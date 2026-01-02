"""
Preemption: Agent interruption, checkpoint, and resumption capabilities.
Enables high-priority agents to preempt lower-priority running agents.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set

if TYPE_CHECKING:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.proposals import AsyncEventBus, Event

logger = logging.getLogger("Preemption")


class CancellationState(Enum):
    """State of a cancellation request."""

    NONE = "none"  # No cancellation requested
    REQUESTED = "requested"  # Cancellation requested, not acknowledged
    ACKNOWLEDGED = "acknowledged"  # Agent acknowledged, will stop
    COMPLETED = "completed"  # Agent has stopped


@dataclass
class AgentCheckpoint:
    """
    Checkpoint of an agent's state for resumption.

    Allows agents to save their progress and resume
    after being preempted.
    """

    agent_name: str
    checkpoint_id: str
    state_snapshot: Dict[str, Any]
    progress: float  # 0.0 to 1.0
    timestamp: str
    resumable: bool = True
    reason: str = ""
    context_hash: str = ""  # To validate context hasn't changed

    def is_valid(self, current_context_hash: str) -> bool:
        """Check if checkpoint is still valid."""
        if not self.resumable:
            return False
        if self.context_hash and self.context_hash != current_context_hash:
            return False
        return True


@dataclass
class PreemptionEvent:
    """Record of a preemption event."""

    preempted_agent: str
    preempting_agent: str
    reason: str
    priority_delta: int  # Difference in priority
    timestamp: str
    checkpoint_created: bool = False
    resumed: bool = False


@dataclass
class CancellationRequest:
    """Request to cancel an agent's execution."""

    agent_name: str
    reason: str
    priority: int
    requester: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    timeout_seconds: float = 10.0


class PreemptionManager:
    """
    Manages agent interruption, checkpointing, and resumption.

    Features:
    - Priority-based preemption
    - Graceful shutdown with timeout
    - Checkpoint/resume capability
    - Cancellation request protocol
    """

    def __init__(self, event_bus: Optional["AsyncEventBus"] = None):
        self._event_bus = event_bus
        self._running_agents: Dict[str, asyncio.Task] = {}
        self._agent_priorities: Dict[str, int] = {}
        self._checkpoints: Dict[str, AgentCheckpoint] = {}
        self._cancellation_states: Dict[str, CancellationState] = {}
        self._cancellation_requests: Dict[str, CancellationRequest] = {}
        self._preemption_history: List[PreemptionEvent] = []
        self._cancelled_agents: Set[str] = set()

        # Callbacks
        self._on_preempt_callbacks: Dict[str, Callable] = {}
        self._on_resume_callbacks: Dict[str, Callable] = {}

    def register_running_agent(
        self,
        agent_name: str,
        task: asyncio.Task,
        priority: int = 5
    ) -> None:
        """Register a running agent with its task."""
        self._running_agents[agent_name] = task
        self._agent_priorities[agent_name] = priority
        self._cancellation_states[agent_name] = CancellationState.NONE
        logger.debug(f"Registered running agent: {agent_name} (priority: {priority})")

    def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent when it completes."""
        self._running_agents.pop(agent_name, None)
        self._agent_priorities.pop(agent_name, None)
        self._cancellation_states.pop(agent_name, None)
        self._cancellation_requests.pop(agent_name, None)
        logger.debug(f"Unregistered agent: {agent_name}")

    def set_on_preempt_callback(
        self,
        agent_name: str,
        callback: Callable[[str], None]
    ) -> None:
        """Set callback to be called when agent is preempted."""
        self._on_preempt_callbacks[agent_name] = callback

    def set_on_resume_callback(
        self,
        agent_name: str,
        callback: Callable[[AgentCheckpoint], None]
    ) -> None:
        """Set callback to be called when agent resumes."""
        self._on_resume_callbacks[agent_name] = callback

    async def preempt_agent(
        self,
        agent_name: str,
        reason: str,
        preempting_agent: str,
        preempting_priority: int
    ) -> bool:
        """
        Attempt to preempt a running agent.

        Args:
            agent_name: Agent to preempt
            reason: Why preemption is needed
            preempting_agent: Name of higher-priority agent
            preempting_priority: Priority of preempting agent

        Returns:
            True if preemption successful, False otherwise
        """
        if agent_name not in self._running_agents:
            logger.warning(f"Cannot preempt {agent_name}: not running")
            return False

        current_priority = self._agent_priorities.get(agent_name, 5)
        priority_delta = preempting_priority - current_priority

        if priority_delta <= 0:
            logger.info(
                f"Preemption denied: {preempting_agent} (p={preempting_priority}) "
                f"cannot preempt {agent_name} (p={current_priority})"
            )
            return False

        logger.info(
            f"Preempting {agent_name} for {preempting_agent} "
            f"(priority delta: +{priority_delta})"
        )

        # Request cancellation
        self.request_cancellation(
            agent_name,
            reason,
            preempting_priority,
            preempting_agent
        )

        # Wait for acknowledgment or timeout
        acknowledged = await self._wait_for_acknowledgment(agent_name, timeout=5.0)

        if not acknowledged:
            # Force cancel
            logger.warning(f"Agent {agent_name} did not acknowledge - forcing cancellation")
            await self._force_cancel(agent_name)

        # Record event
        checkpoint_created = agent_name in self._checkpoints
        self._preemption_history.append(PreemptionEvent(
            preempted_agent=agent_name,
            preempting_agent=preempting_agent,
            reason=reason,
            priority_delta=priority_delta,
            timestamp=datetime.now().isoformat(),
            checkpoint_created=checkpoint_created
        ))

        # Call callback
        if agent_name in self._on_preempt_callbacks:
            try:
                self._on_preempt_callbacks[agent_name](reason)
            except Exception as e:
                logger.error(f"Preempt callback failed: {e}")

        # Publish event if event bus available
        if self._event_bus:
            from skincare_agent_system.core.proposals import Event, EventType
            await self._event_bus.publish(Event(
                type="agent_preempted",
                source="PreemptionManager",
                payload={
                    "preempted_agent": agent_name,
                    "preempting_agent": preempting_agent,
                    "reason": reason
                }
            ))

        return True

    def request_cancellation(
        self,
        agent_name: str,
        reason: str,
        priority: int = 10,
        requester: str = "system"
    ) -> None:
        """Request an agent to cancel its execution."""
        request = CancellationRequest(
            agent_name=agent_name,
            reason=reason,
            priority=priority,
            requester=requester
        )
        self._cancellation_requests[agent_name] = request
        self._cancellation_states[agent_name] = CancellationState.REQUESTED
        logger.info(f"Cancellation requested for {agent_name}: {reason}")

    def is_cancellation_requested(self, agent_name: str) -> bool:
        """Check if cancellation is requested for an agent."""
        return self._cancellation_states.get(agent_name) == CancellationState.REQUESTED

    def get_cancellation_request(
        self,
        agent_name: str
    ) -> Optional[CancellationRequest]:
        """Get the cancellation request details."""
        return self._cancellation_requests.get(agent_name)

    def acknowledge_cancellation(self, agent_name: str) -> None:
        """Agent acknowledges cancellation request."""
        if agent_name in self._cancellation_states:
            self._cancellation_states[agent_name] = CancellationState.ACKNOWLEDGED
            logger.info(f"Agent {agent_name} acknowledged cancellation")

    def complete_cancellation(self, agent_name: str) -> None:
        """Mark cancellation as complete."""
        if agent_name in self._cancellation_states:
            self._cancellation_states[agent_name] = CancellationState.COMPLETED
            self._cancelled_agents.add(agent_name)
            logger.info(f"Agent {agent_name} cancellation complete")

    async def checkpoint_agent(
        self,
        agent: "BaseAgent",
        state_snapshot: Dict[str, Any],
        progress: float,
        reason: str = ""
    ) -> AgentCheckpoint:
        """
        Create a checkpoint for an agent.

        Args:
            agent: The agent to checkpoint
            state_snapshot: Agent's internal state
            progress: Progress through current task (0.0-1.0)
            reason: Why checkpoint was created

        Returns:
            The created checkpoint
        """
        import hashlib
        import json

        # Generate checkpoint ID
        checkpoint_id = f"{agent.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Hash current context for validation
        context_hash = ""
        if hasattr(agent, '_context') and agent._context:
            context_str = json.dumps(
                agent._context.model_dump() if hasattr(agent._context, 'model_dump')
                else str(agent._context),
                sort_keys=True,
                default=str
            )
            context_hash = hashlib.md5(context_str.encode()).hexdigest()[:8]

        checkpoint = AgentCheckpoint(
            agent_name=agent.name,
            checkpoint_id=checkpoint_id,
            state_snapshot=state_snapshot,
            progress=progress,
            timestamp=datetime.now().isoformat(),
            resumable=True,
            reason=reason,
            context_hash=context_hash
        )

        self._checkpoints[agent.name] = checkpoint
        logger.info(f"Created checkpoint for {agent.name}: {checkpoint_id} ({progress:.1%})")

        return checkpoint

    def get_checkpoint(self, agent_name: str) -> Optional[AgentCheckpoint]:
        """Get the most recent checkpoint for an agent."""
        return self._checkpoints.get(agent_name)

    def has_checkpoint(self, agent_name: str) -> bool:
        """Check if agent has a valid checkpoint."""
        return agent_name in self._checkpoints

    async def resume_agent(
        self,
        agent_name: str,
        context_hash: str = ""
    ) -> Optional[AgentCheckpoint]:
        """
        Resume an agent from its checkpoint.

        Args:
            agent_name: Agent to resume
            context_hash: Optional hash to validate context

        Returns:
            The checkpoint if resumable, None otherwise
        """
        checkpoint = self._checkpoints.get(agent_name)

        if not checkpoint:
            logger.warning(f"No checkpoint found for {agent_name}")
            return None

        if not checkpoint.is_valid(context_hash):
            logger.warning(f"Checkpoint for {agent_name} is no longer valid")
            return None

        # Clear cancellation state
        self._cancellation_states[agent_name] = CancellationState.NONE
        self._cancelled_agents.discard(agent_name)

        # Update preemption history
        for event in reversed(self._preemption_history):
            if event.preempted_agent == agent_name and not event.resumed:
                event.resumed = True
                break

        # Call callback
        if agent_name in self._on_resume_callbacks:
            try:
                self._on_resume_callbacks[agent_name](checkpoint)
            except Exception as e:
                logger.error(f"Resume callback failed: {e}")

        logger.info(f"Resuming agent {agent_name} from {checkpoint.checkpoint_id}")
        return checkpoint

    def discard_checkpoint(self, agent_name: str) -> None:
        """Discard a checkpoint."""
        if agent_name in self._checkpoints:
            del self._checkpoints[agent_name]
            logger.info(f"Discarded checkpoint for {agent_name}")

    async def graceful_shutdown(
        self,
        agent_name: str,
        timeout: float = 5.0,
        create_checkpoint: bool = True
    ) -> bool:
        """
        Gracefully shut down an agent.

        Args:
            agent_name: Agent to shut down
            timeout: Maximum time to wait
            create_checkpoint: Whether to create checkpoint before shutdown

        Returns:
            True if graceful shutdown succeeded, False if forced
        """
        if agent_name not in self._running_agents:
            return True

        logger.info(f"Initiating graceful shutdown of {agent_name} (timeout: {timeout}s)")

        # Request cancellation
        self.request_cancellation(
            agent_name,
            "graceful_shutdown",
            priority=100,
            requester="system"
        )

        # Wait for acknowledgment
        acknowledged = await self._wait_for_acknowledgment(agent_name, timeout=timeout)

        if acknowledged:
            # Wait for completion
            task = self._running_agents.get(agent_name)
            if task:
                try:
                    await asyncio.wait_for(task, timeout=timeout)
                    self.complete_cancellation(agent_name)
                    return True
                except asyncio.TimeoutError:
                    pass

        # Force cancel
        await self._force_cancel(agent_name)
        return False

    async def _wait_for_acknowledgment(
        self,
        agent_name: str,
        timeout: float
    ) -> bool:
        """Wait for agent to acknowledge cancellation."""
        start = datetime.now()

        while (datetime.now() - start).total_seconds() < timeout:
            state = self._cancellation_states.get(agent_name)
            if state in [CancellationState.ACKNOWLEDGED, CancellationState.COMPLETED]:
                return True
            await asyncio.sleep(0.1)

        return False

    async def _force_cancel(self, agent_name: str) -> None:
        """Force cancel an agent's task."""
        task = self._running_agents.get(agent_name)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.complete_cancellation(agent_name)
        self.unregister_agent(agent_name)
        logger.warning(f"Force cancelled agent: {agent_name}")

    def can_preempt(self, agent_name: str, new_priority: int) -> bool:
        """Check if an agent can be preempted by given priority."""
        if agent_name not in self._running_agents:
            return False
        current_priority = self._agent_priorities.get(agent_name, 5)
        return new_priority > current_priority

    def get_running_agents(self) -> List[str]:
        """Get list of running agents."""
        return list(self._running_agents.keys())

    def get_preemption_history(self) -> List[PreemptionEvent]:
        """Get history of preemption events."""
        return self._preemption_history.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get preemption manager statistics."""
        return {
            "running_agents": len(self._running_agents),
            "active_checkpoints": len(self._checkpoints),
            "total_preemptions": len(self._preemption_history),
            "resumed_count": sum(1 for p in self._preemption_history if p.resumed),
            "cancelled_agents": len(self._cancelled_agents),
            "pending_cancellations": sum(
                1 for s in self._cancellation_states.values()
                if s == CancellationState.REQUESTED
            )
        }


# Singleton instance
_preemption_manager: Optional[PreemptionManager] = None


def get_preemption_manager(
    event_bus: Optional["AsyncEventBus"] = None
) -> PreemptionManager:
    """Get or create the preemption manager singleton."""
    global _preemption_manager

    if _preemption_manager is None:
        _preemption_manager = PreemptionManager(event_bus)

    return _preemption_manager


def reset_preemption_manager() -> None:
    """Reset the preemption manager singleton (for testing)."""
    global _preemption_manager
    _preemption_manager = None
