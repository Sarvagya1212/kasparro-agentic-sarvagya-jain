"""
Agent Activation: Spontaneous agent activation independent of orchestrator.
Enables agents to wake up based on events without waiting for orchestrator turns.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.proposals import Event, EventBus

logger = logging.getLogger("AgentActivation")


class AgentState(Enum):
    """State of an agent in the activation system."""

    SLEEPING = "sleeping"  # Not active, not polling
    POLLING = "polling"  # Actively polling for events
    ACTIVE = "active"  # Currently executing
    WAITING = "waiting"  # Waiting for specific event
    SUSPENDED = "suspended"  # Temporarily suspended
    TERMINATED = "terminated"  # Permanently stopped


@dataclass
class ActivationTrigger:
    """Defines when an agent should wake up."""

    event_type: str
    condition: Optional[Callable[["Event"], bool]] = None
    priority: int = 5  # Higher = more urgent wake-up
    cooldown_seconds: float = 0.0  # Minimum time between activations
    description: str = ""


@dataclass
class ActivationRequest:
    """Request to activate an agent."""

    agent_name: str
    reason: str
    priority: int
    trigger: Optional[ActivationTrigger] = None
    event: Optional["Event"] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __lt__(self, other: "ActivationRequest") -> bool:
        """For priority queue ordering (higher priority = processed first)."""
        return self.priority > other.priority


@dataclass
class AgentWakeRecord:
    """Record of an agent activation."""

    agent_name: str
    wake_time: str
    reason: str
    trigger_event: Optional[str] = None
    duration_ms: Optional[float] = None


class ActivationQueue:
    """
    Priority queue for agent activation requests.
    Higher priority agents are activated first.
    """

    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._pending: Dict[str, ActivationRequest] = {}

    async def put(self, request: ActivationRequest) -> None:
        """Add activation request to queue."""
        # Avoid duplicate requests for same agent
        if request.agent_name in self._pending:
            existing = self._pending[request.agent_name]
            if request.priority > existing.priority:
                # Replace with higher priority request
                self._pending[request.agent_name] = request
            return

        self._pending[request.agent_name] = request
        await self._queue.put(request)

    async def get(self) -> ActivationRequest:
        """Get next activation request (blocks if empty)."""
        request = await self._queue.get()
        self._pending.pop(request.agent_name, None)
        return request

    def get_nowait(self) -> Optional[ActivationRequest]:
        """Get next request without blocking."""
        try:
            request = self._queue.get_nowait()
            self._pending.pop(request.agent_name, None)
            return request
        except asyncio.QueueEmpty:
            return None

    def is_pending(self, agent_name: str) -> bool:
        """Check if agent has pending activation."""
        return agent_name in self._pending

    def __len__(self) -> int:
        return self._queue.qsize()


class AgentActivator:
    """
    Manages agent activation independently of orchestrator.

    Features:
    - Event-based wake triggers
    - Priority-based activation queue
    - Agent state management
    - Polling mechanism for autonomous behavior
    """

    def __init__(self, event_bus: "EventBus"):
        self._event_bus = event_bus
        self._agents: Dict[str, "BaseAgent"] = {}
        self._agent_states: Dict[str, AgentState] = {}
        self._agent_triggers: Dict[str, List[ActivationTrigger]] = {}
        self._last_activation: Dict[str, datetime] = {}
        self._activation_queue = ActivationQueue()
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self._wake_history: List[AgentWakeRecord] = []
        self._is_running = False
        self._processor_task: Optional[asyncio.Task] = None

    def register_agent(
        self,
        agent: "BaseAgent",
        triggers: List[ActivationTrigger],
        initial_state: AgentState = AgentState.SLEEPING,
    ) -> None:
        """Register an agent with its activation triggers."""
        self._agents[agent.name] = agent
        self._agent_states[agent.name] = initial_state
        self._agent_triggers[agent.name] = triggers

        # Subscribe to trigger events
        for trigger in triggers:
            self._event_bus.subscribe(
                trigger.event_type,
                lambda e, t=trigger, a=agent.name: self._on_trigger_event(a, t, e),
            )

        logger.info(
            f"Registered agent {agent.name} with {len(triggers)} triggers, "
            f"initial state: {initial_state.value}"
        )

    async def start(self) -> None:
        """Start the activation system."""
        self._is_running = True
        self._processor_task = asyncio.create_task(self._process_queue())
        logger.info("Agent activation system started")

    async def stop(self) -> None:
        """Stop the activation system."""
        self._is_running = False

        # Cancel all polling tasks
        for task in self._polling_tasks.values():
            task.cancel()

        # Cancel processor
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        # Set all agents to terminated
        for name in self._agents:
            self._agent_states[name] = AgentState.TERMINATED

        self._polling_tasks.clear()
        logger.info("Agent activation system stopped")

    def get_agent_state(self, agent_name: str) -> AgentState:
        """Get current state of an agent."""
        return self._agent_states.get(agent_name, AgentState.TERMINATED)

    def set_agent_state(self, agent_name: str, state: AgentState) -> None:
        """Set agent state."""
        if agent_name in self._agent_states:
            old_state = self._agent_states[agent_name]
            self._agent_states[agent_name] = state
            logger.debug(f"Agent {agent_name}: {old_state.value} -> {state.value}")

    async def wake_agent(self, agent_name: str, reason: str, priority: int = 5) -> bool:
        """
        Request to wake an agent.

        Returns:
            True if wake request was queued, False if agent can't be woken
        """
        if agent_name not in self._agents:
            logger.warning(f"Cannot wake unknown agent: {agent_name}")
            return False

        state = self._agent_states[agent_name]
        if state == AgentState.TERMINATED:
            logger.warning(f"Cannot wake terminated agent: {agent_name}")
            return False

        if state == AgentState.ACTIVE:
            logger.debug(f"Agent {agent_name} already active")
            return True

        # Check cooldown
        if agent_name in self._last_activation:
            triggers = self._agent_triggers.get(agent_name, [])
            min_cooldown = min((t.cooldown_seconds for t in triggers), default=0)
            elapsed = (
                datetime.now() - self._last_activation[agent_name]
            ).total_seconds()
            if elapsed < min_cooldown:
                logger.debug(
                    f"Agent {agent_name} in cooldown ({elapsed:.1f}s < {min_cooldown}s)"
                )
                return False

        # Queue activation request
        request = ActivationRequest(
            agent_name=agent_name, reason=reason, priority=priority
        )
        await self._activation_queue.put(request)
        logger.info(
            f"Queued wake request for {agent_name}: {reason} (priority: {priority})"
        )
        return True

    async def sleep_agent(self, agent_name: str) -> None:
        """Put an agent to sleep."""
        if agent_name not in self._agents:
            return

        # Cancel polling if running
        if agent_name in self._polling_tasks:
            self._polling_tasks[agent_name].cancel()
            try:
                await self._polling_tasks[agent_name]
            except asyncio.CancelledError:
                pass
            del self._polling_tasks[agent_name]

        self._agent_states[agent_name] = AgentState.SLEEPING
        logger.info(f"Agent {agent_name} is now sleeping")

    async def start_polling(self, agent_name: str, poll_interval: float = 1.0) -> None:
        """Start polling for an agent."""
        if agent_name not in self._agents:
            return

        if agent_name in self._polling_tasks:
            return  # Already polling

        self._agent_states[agent_name] = AgentState.POLLING

        async def poll_loop():
            while self._is_running:
                try:
                    await asyncio.sleep(poll_interval)
                    # Agent can check for conditions here
                    agent = self._agents[agent_name]
                    if hasattr(agent, "poll_for_activation"):
                        should_activate = await agent.poll_for_activation()
                        if should_activate:
                            await self.wake_agent(
                                agent_name, "Self-activated via polling", priority=3
                            )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Polling error for {agent_name}: {e}")

        task = asyncio.create_task(poll_loop())
        self._polling_tasks[agent_name] = task
        logger.info(f"Started polling for {agent_name} (interval: {poll_interval}s)")

    async def stop_polling(self, agent_name: str) -> None:
        """Stop polling for an agent."""
        if agent_name in self._polling_tasks:
            self._polling_tasks[agent_name].cancel()
            try:
                await self._polling_tasks[agent_name]
            except asyncio.CancelledError:
                pass
            del self._polling_tasks[agent_name]
            logger.info(f"Stopped polling for {agent_name}")

    def _on_trigger_event(
        self, agent_name: str, trigger: ActivationTrigger, event: "Event"
    ) -> None:
        """Handle a trigger event."""
        # Check condition if specified
        if trigger.condition and not trigger.condition(event):
            return

        # Queue wake request (can't await in sync callback)
        asyncio.create_task(
            self.wake_agent(
                agent_name,
                f"Triggered by {event.type} event",
                priority=trigger.priority,
            )
        )

    async def _process_queue(self) -> None:
        """Process the activation queue."""
        while self._is_running:
            try:
                # Get next activation request
                request = await asyncio.wait_for(
                    self._activation_queue.get(), timeout=1.0
                )

                await self._activate_agent(request)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    async def _activate_agent(self, request: ActivationRequest) -> None:
        """Activate an agent."""
        agent_name = request.agent_name
        agent = self._agents.get(agent_name)

        if not agent:
            return

        # Update state
        self._agent_states[agent_name] = AgentState.ACTIVE
        self._last_activation[agent_name] = datetime.now()

        start_time = datetime.now()
        logger.info(f"Activating agent {agent_name}: {request.reason}")

        try:
            # Call agent's wake-up handler if it has one
            if hasattr(agent, "on_wake"):
                await agent.on_wake(request.reason)

            # Record wake
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self._wake_history.append(
                AgentWakeRecord(
                    agent_name=agent_name,
                    wake_time=start_time.isoformat(),
                    reason=request.reason,
                    trigger_event=request.event.type if request.event else None,
                    duration_ms=duration,
                )
            )

        except Exception as e:
            logger.error(f"Agent activation failed for {agent_name}: {e}")

        finally:
            # Return to polling/sleeping state
            if agent_name in self._polling_tasks:
                self._agent_states[agent_name] = AgentState.POLLING
            else:
                self._agent_states[agent_name] = AgentState.SLEEPING

    def get_active_agents(self) -> List[str]:
        """Get list of currently active agents."""
        return [
            name
            for name, state in self._agent_states.items()
            if state == AgentState.ACTIVE
        ]

    def get_polling_agents(self) -> List[str]:
        """Get list of agents currently polling."""
        return [
            name
            for name, state in self._agent_states.items()
            if state == AgentState.POLLING
        ]

    def get_wake_history(self, limit: int = 50) -> List[AgentWakeRecord]:
        """Get recent wake history."""
        return self._wake_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get activation system statistics."""
        state_counts = {}
        for state in AgentState:
            state_counts[state.value] = sum(
                1 for s in self._agent_states.values() if s == state
            )

        return {
            "total_agents": len(self._agents),
            "state_counts": state_counts,
            "pending_activations": len(self._activation_queue),
            "total_wakes": len(self._wake_history),
            "is_running": self._is_running,
        }


# Singleton instance
_activator_instance: Optional[AgentActivator] = None


def get_agent_activator(event_bus: Optional["EventBus"] = None) -> AgentActivator:
    """Get or create the agent activator singleton."""
    global _activator_instance

    if _activator_instance is None:
        if event_bus is None:
            from skincare_agent_system.core.proposals import EventBus

            event_bus = EventBus()
        _activator_instance = AgentActivator(event_bus)

    return _activator_instance


def reset_agent_activator() -> None:
    """Reset the activator singleton (for testing)."""
    global _activator_instance
    _activator_instance = None
