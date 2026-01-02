"""
Agent Action Proposals: True Agent Autonomy.
Agents propose actions based on context assessment, not orchestrator commands.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.core.models import AgentContext

logger = logging.getLogger("Proposals")


@dataclass
class AgentProposal:
    """
    A proposal from an agent about what it can do.
    Demonstrates agent autonomy - agents assess context and propose actions.
    """

    agent_name: str
    action: str
    confidence: float  # 0.0 - 1.0 (higher = more confident)
    reason: str
    preconditions_met: bool
    priority: int = 0  # Higher = more urgent
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __repr__(self):
        status = "✓" if self.preconditions_met else "✗"
        return (
            f"[{status}] {self.agent_name}: {self.action} "
            f"(confidence: {self.confidence:.2f}) - {self.reason}"
        )


class ProposalSystem:
    """
    Collects and evaluates proposals from agents.
    The Coordinator uses this to dynamically select the next agent.
    """

    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._proposal_log: List[Dict] = []

    def register_agent(self, name: str, agent: Any):
        """Register an agent that can make proposals."""
        self._agents[name] = agent
        logger.debug(f"Registered agent for proposals: {name}")

    def collect_proposals(self, context: "AgentContext") -> List[AgentProposal]:
        """
        Ask all registered agents what they can do.
        Each agent independently assesses the context and proposes actions.
        """
        proposals = []

        for name, agent in self._agents.items():
            try:
                if hasattr(agent, "propose"):
                    proposal = agent.propose(context)
                    if proposal and proposal.preconditions_met:
                        proposals.append(proposal)
                        logger.debug(f"Proposal from {name}: {proposal}")
            except Exception as e:
                logger.warning(f"Agent {name} failed to propose: {e}")

        # Log collection
        self._proposal_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "proposals_count": len(proposals),
                "agents_queried": len(self._agents),
                "proposals": [
                    {
                        "agent": p.agent_name,
                        "action": p.action,
                        "confidence": p.confidence,
                    }
                    for p in proposals
                ],
            }
        )

        logger.info(
            f"Collected {len(proposals)} valid proposals from {len(self._agents)} agents"
        )
        return proposals

    async def collect_proposals_async(
        self, context: "AgentContext"
    ) -> List[AgentProposal]:
        """
        PHASE 1: Async proposal collection via asyncio.gather.
        Collects proposals from all agents CONCURRENTLY for better performance.
        """
        import asyncio

        async def get_proposal(name: str, agent: Any) -> Optional[AgentProposal]:
            try:
                if hasattr(agent, "propose"):
                    # Run propose in executor if sync
                    loop = asyncio.get_event_loop()
                    proposal = await loop.run_in_executor(None, agent.propose, context)
                    if proposal and proposal.preconditions_met:
                        logger.debug(f"Proposal from {name}: {proposal}")
                        return proposal
            except Exception as e:
                logger.warning(f"Agent {name} failed to propose: {e}")
            return None

        # Collect proposals concurrently
        tasks = [get_proposal(name, agent) for name, agent in self._agents.items()]
        results = await asyncio.gather(*tasks)

        # Filter out None results
        proposals = [p for p in results if p is not None]

        # Log collection
        self._proposal_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "proposals_count": len(proposals),
                "agents_queried": len(self._agents),
                "async": True,
                "proposals": [
                    {
                        "agent": p.agent_name,
                        "action": p.action,
                        "confidence": p.confidence,
                    }
                    for p in proposals
                ],
            }
        )

        logger.info(
            f"Collected {len(proposals)} valid proposals from {len(self._agents)} agents (ASYNC)"
        )
        return proposals

    def select_best_proposal(
        self, proposals: List[AgentProposal], strategy: str = "highest_confidence"
    ) -> Optional[AgentProposal]:
        """
        Select the best proposal using a strategy.

        Strategies:
        - "highest_confidence": Pick proposal with highest confidence
        - "highest_priority": Pick proposal with highest priority
        - "priority_then_confidence": Priority first, then confidence
        """
        if not proposals:
            return None

        # Filter to only valid proposals
        valid = [p for p in proposals if p.preconditions_met and p.confidence > 0]
        if not valid:
            return None

        if strategy == "highest_confidence":
            return max(valid, key=lambda p: p.confidence)
        elif strategy == "highest_priority":
            return max(valid, key=lambda p: p.priority)
        elif strategy == "priority_then_confidence":
            return max(valid, key=lambda p: (p.priority, p.confidence))
        else:
            return max(valid, key=lambda p: p.confidence)

    def negotiate_proposals(
        self, proposals: List[AgentProposal], max_rounds: int = 3
    ) -> List[AgentProposal]:
        """
        PHASE 5: Multi-round negotiation protocol.
        Agents adjust confidence based on competition.

        Each round:
        1. Agents see all competing proposals
        2. Agents can adjust their confidence
        3. Low-confidence proposals drop out
        """
        if len(proposals) <= 1:
            return proposals

        negotiation_log = []
        current_proposals = proposals.copy()

        for round_num in range(max_rounds):
            round_data = {
                "round": round_num + 1,
                "proposals_count": len(current_proposals),
                "adjustments": [],
            }

            # Calculate competition factor for each proposal
            total_confidence = sum(p.confidence for p in current_proposals)
            avg_confidence = (
                total_confidence / len(current_proposals) if current_proposals else 0
            )

            adjusted_proposals = []
            for proposal in current_proposals:
                # PHASE 5: Confidence adjustment based on competition
                competition_factor = self._calculate_competition_factor(
                    proposal, current_proposals, avg_confidence
                )

                original_conf = proposal.confidence
                new_conf = min(1.0, max(0.1, proposal.confidence * competition_factor))

                # Create adjusted proposal
                adjusted = AgentProposal(
                    agent_name=proposal.agent_name,
                    action=proposal.action,
                    confidence=new_conf,
                    reason=f"{proposal.reason} [negotiated R{round_num + 1}]",
                    preconditions_met=proposal.preconditions_met,
                    priority=proposal.priority,
                )

                round_data["adjustments"].append(
                    {
                        "agent": proposal.agent_name,
                        "before": original_conf,
                        "after": new_conf,
                        "factor": competition_factor,
                    }
                )

                # Drop proposals with very low confidence after adjustment
                if new_conf >= 0.15:
                    adjusted_proposals.append(adjusted)
                else:
                    logger.debug(
                        f"Proposal from {proposal.agent_name} dropped (conf: {new_conf:.2f})"
                    )

            negotiation_log.append(round_data)
            current_proposals = adjusted_proposals

            # Early termination if consensus reached
            if len(current_proposals) <= 1:
                break

            # Check if confidences have stabilized
            if round_num > 0:
                prev_confidences = [
                    r["after"] for r in negotiation_log[-2]["adjustments"]
                ]
                curr_confidences = [p.confidence for p in current_proposals]
                if len(prev_confidences) == len(curr_confidences):
                    if all(
                        abs(a - b) < 0.05
                        for a, b in zip(
                            sorted(prev_confidences), sorted(curr_confidences)
                        )
                    ):
                        logger.debug(
                            f"Negotiation stabilized after {round_num + 1} rounds"
                        )
                        break

        logger.info(
            f"Negotiation complete: {len(proposals)} -> {len(current_proposals)} proposals over {len(negotiation_log)} rounds"
        )
        return current_proposals

    def _calculate_competition_factor(
        self,
        proposal: AgentProposal,
        all_proposals: List[AgentProposal],
        avg_confidence: float,
    ) -> float:
        """
        PHASE 5: Calculate competition adjustment factor.
        - High-confidence proposals against weak competition get boosted
        - Low-confidence proposals against strong competition get reduced
        """
        if proposal.confidence >= avg_confidence:
            # Above average - slight boost
            boost = 1.0 + 0.1 * (
                (proposal.confidence - avg_confidence) / max(0.1, avg_confidence)
            )
            return min(1.2, boost)
        else:
            # Below average - reduction proportional to gap
            reduction = 1.0 - 0.15 * (
                (avg_confidence - proposal.confidence) / max(0.1, avg_confidence)
            )
            return max(0.7, reduction)

    def form_coalition(
        self, proposals: List[AgentProposal], task_complexity: float = 0.5
    ) -> Optional[Dict]:
        """
        PHASE 5: Coalition formation for complex tasks.
        When task is complex, multiple agents can form a coalition.

        Returns coalition structure if beneficial, None otherwise.
        """
        if task_complexity < 0.6 or len(proposals) < 2:
            return None  # Simple tasks don't need coalitions

        # Sort by confidence
        sorted_proposals = sorted(proposals, key=lambda p: p.confidence, reverse=True)

        # Form coalition from top proposals
        coalition_size = min(3, len(sorted_proposals))
        coalition_members = sorted_proposals[:coalition_size]

        # Calculate combined strength
        combined_confidence = (
            sum(p.confidence for p in coalition_members) / coalition_size
        )

        coalition = {
            "type": "coalition",
            "leader": coalition_members[0].agent_name,
            "members": [p.agent_name for p in coalition_members],
            "combined_confidence": combined_confidence,
            "actions": [p.action for p in coalition_members],
            "task_complexity": task_complexity,
        }

        logger.info(
            f"Coalition formed: {coalition['members']} (strength: {combined_confidence:.2f})"
        )
        return coalition

    def get_proposal_log(self) -> List[Dict]:
        """Get history of proposal collections."""
        return self._proposal_log.copy()


# Event types for event-driven coordination
class EventType:
    """Standard event types for agent communication."""

    DATA_LOADED = "data_loaded"
    SYNTHETIC_DATA_GENERATED = "synthetic_data_generated"
    ANALYSIS_COMPLETE = "analysis_complete"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    GENERATION_COMPLETE = "generation_complete"
    VERIFICATION_COMPLETE = "verification_complete"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class Event:
    """Event for agent-to-agent communication."""

    type: str
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EventBus:
    """
    Event bus for agent communication (synchronous).
    Enables event-driven coordination instead of direct calls.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[Event] = []

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type}")

    def publish(self, event: Event):
        """Publish an event to all subscribers."""
        self._event_log.append(event)
        logger.info(f"Event published: {event.type} from {event.source}")

        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.type}: {e}")

    def get_event_log(self) -> List[Event]:
        """Get event history."""
        return self._event_log.copy()


class AsyncEventBus:
    """
    Async event bus with message queue for high-throughput event handling.
    Enables concurrent event processing and async handler execution.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[Event] = []
        self._queue: Optional[Any] = None  # asyncio.Queue
        self._running = False
        self._processor_task: Optional[Any] = None

    async def start(self):
        """Start event processing loop."""
        import asyncio

        self._queue = asyncio.Queue()
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("AsyncEventBus started")

    async def stop(self):
        """Stop event processing."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncEventBus stopped")

    async def _process_events(self):
        """Process events from queue."""
        import asyncio

        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    async def publish(self, event: Event):
        """Publish event to queue for async processing."""
        self._event_log.append(event)
        if self._queue:
            await self._queue.put(event)
            logger.info(f"Event queued: {event.type} from {event.source}")
        else:
            logger.warning(f"AsyncEventBus not started, event dropped: {event.type}")

    async def _dispatch(self, event: Event):
        """Dispatch event to all subscribers concurrently."""
        import asyncio

        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return

        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(handler(event))
            else:
                # Wrap sync handlers in executor
                loop = asyncio.get_event_loop()
                tasks.append(loop.run_in_executor(None, handler, event))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Handler {i} failed for {event.type}: {result}")

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type (supports both sync and async handlers)."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type}")

    def get_event_log(self) -> List[Event]:
        """Get event history."""
        return self._event_log.copy()

    async def wait_for_queue_empty(self):
        """Wait for all queued events to be processed."""
        if self._queue:
            await self._queue.join()


@dataclass
class Goal:
    """A goal that agents work toward."""

    id: str
    description: str
    success_criteria: List[str]
    priority: int = 1
    achieved: bool = False
    assigned_agent: Optional[str] = None


class GoalManager:
    """
    Manages goals that agents work toward.
    Enables goal-based reasoning and workflow termination.
    """

    def __init__(self):
        self._goals: List[Goal] = []

    def add_goal(self, goal: Goal):
        """Add a goal."""
        self._goals.append(goal)
        logger.info(f"Goal added: {goal.description}")

    def update_progress(self, context: "AgentContext"):
        """Update goal progress based on context state."""
        for goal in self._goals:
            if not goal.achieved:
                goal.achieved = self.is_goal_achieved(goal.id, context)
                if goal.achieved:
                    logger.info(f"✓ Goal achieved: {goal.description}")

    def all_goals_achieved(self, context: "AgentContext") -> bool:
        """Check if all goals are achieved."""
        self.update_progress(context)
        achieved_count = sum(1 for g in self._goals if g.achieved)
        total_count = len(self._goals)
        logger.info(f"Goal progress: {achieved_count}/{total_count} achieved")
        return all(g.achieved for g in self._goals)

    def mark_achieved(self, goal_id: str):
        """Mark a goal as achieved."""
        for goal in self._goals:
            if goal.id == goal_id:
                goal.achieved = True
                logger.info(f"Goal achieved: {goal.description}")
                return

    def get_pending_goals(self) -> List[Goal]:
        """Get goals not yet achieved."""
        return [g for g in self._goals if not g.achieved]

    def get_highest_priority_goal(self) -> Optional[Goal]:
        """Get the highest priority pending goal."""
        pending = self.get_pending_goals()
        if not pending:
            return None
        return max(pending, key=lambda g: g.priority)

    def is_goal_achieved(self, goal_id: str, context: "AgentContext") -> bool:
        """Check if a goal is achieved based on context."""
        for goal in self._goals:
            if goal.id == goal_id:
                # Check success criteria
                for criterion in goal.success_criteria:
                    if criterion == "product_data_loaded":
                        if not context.product_data:
                            return False
                    elif criterion == "comparison_data_loaded":
                        if not context.comparison_data:
                            return False
                    elif criterion == "analysis_complete":
                        if not context.analysis_results:
                            return False
                    elif criterion == "validation_passed":
                        if not context.is_valid:
                            return False
                    elif criterion == "content_generated":
                        # Check if content generation has occurred
                        # This is true if analysis is valid (VerifierAgent ran)
                        if not context.is_valid:
                            return False
                return True
        return False
