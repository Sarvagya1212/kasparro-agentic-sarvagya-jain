"""
Agent Action Proposals: True Agent Autonomy.
Agents propose actions based on context assessment, not orchestrator commands.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .models import AgentContext

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
        self._proposal_log.append({
            "timestamp": datetime.now().isoformat(),
            "proposals_count": len(proposals),
            "agents_queried": len(self._agents),
            "proposals": [
                {
                    "agent": p.agent_name,
                    "action": p.action,
                    "confidence": p.confidence
                }
                for p in proposals
            ]
        })

        logger.info(f"Collected {len(proposals)} valid proposals from {len(self._agents)} agents")
        return proposals

    def select_best_proposal(
        self,
        proposals: List[AgentProposal],
        strategy: str = "highest_confidence"
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
    Event bus for agent communication.
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
    Enables goal-based reasoning.
    """

    def __init__(self):
        self._goals: List[Goal] = []

    def add_goal(self, goal: Goal):
        """Add a goal."""
        self._goals.append(goal)
        logger.info(f"Goal added: {goal.description}")

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
                return True
        return False
