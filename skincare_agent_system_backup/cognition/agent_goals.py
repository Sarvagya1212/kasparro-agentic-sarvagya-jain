"""
Agent Goals: Internal goal state management for autonomous agents.
Enables agents to track their own objectives and derive actions from goals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.core.models import AgentContext

logger = logging.getLogger("AgentGoals")


class GoalStatus(Enum):
    """Status of an agent goal."""

    PENDING = "pending"  # Not yet started
    IN_PROGRESS = "in_progress"  # Currently being worked on
    COMPLETED = "completed"  # Successfully achieved
    FAILED = "failed"  # Failed to achieve
    BLOCKED = "blocked"  # Waiting on external dependency
    CANCELLED = "cancelled"  # Manually cancelled


@dataclass
class GoalProgress:
    """Progress update for a goal."""

    goal_id: str
    progress: float  # 0.0 to 1.0
    status: GoalStatus
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentGoal:
    """
    An agent's internal goal with tracking.

    Goals can have:
    - Success criteria to evaluate completion
    - Priority for ordering
    - Sub-goals for decomposition
    - Callbacks for completion/failure
    """

    id: str
    description: str
    success_criteria: List[str]
    status: GoalStatus = GoalStatus.PENDING
    priority: int = 1  # Higher = more important
    progress: float = 0.0  # 0.0 to 1.0
    parent_goal: Optional[str] = None
    sub_goals: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Callbacks (set after creation)
    on_complete: Optional[Callable[["AgentGoal"], None]] = field(
        default=None, repr=False
    )
    on_fail: Optional[Callable[["AgentGoal", str], None]] = field(
        default=None, repr=False
    )
    on_progress: Optional[Callable[[GoalProgress], None]] = field(
        default=None, repr=False
    )

    def is_terminal(self) -> bool:
        """Check if goal is in a terminal state."""
        return self.status in [
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
        ]

    def can_start(self) -> bool:
        """Check if goal can be started."""
        return self.status == GoalStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for serialization)."""
        return {
            "id": self.id,
            "description": self.description,
            "success_criteria": self.success_criteria,
            "status": self.status.value,
            "priority": self.priority,
            "progress": self.progress,
            "parent_goal": self.parent_goal,
            "sub_goals": self.sub_goals,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


class AgentGoalManager:
    """
    Manages an agent's internal goals.

    Responsibilities:
    - Track goal status and progress
    - Evaluate goal completion criteria
    - Derive next actions from goals
    - Handle goal callbacks
    """

    def __init__(self, agent_name: str):
        self._agent_name = agent_name
        self._goals: Dict[str, AgentGoal] = {}
        self._goal_history: List[GoalProgress] = []

    @property
    def agent_name(self) -> str:
        return self._agent_name

    def add_goal(
        self,
        goal: AgentGoal,
        on_complete: Optional[Callable] = None,
        on_fail: Optional[Callable] = None,
    ) -> None:
        """Add a goal to track."""
        if on_complete:
            goal.on_complete = on_complete
        if on_fail:
            goal.on_fail = on_fail

        self._goals[goal.id] = goal
        logger.info(f"[{self._agent_name}] Added goal: {goal.id} - {goal.description}")

    def add_sub_goal(self, parent_id: str, sub_goal: AgentGoal) -> None:
        """Add a sub-goal to an existing goal."""
        if parent_id not in self._goals:
            raise ValueError(f"Parent goal {parent_id} not found")

        sub_goal.parent_goal = parent_id
        self._goals[parent_id].sub_goals.append(sub_goal.id)
        self.add_goal(sub_goal)
        logger.debug(f"Added sub-goal {sub_goal.id} to {parent_id}")

    def get_goal(self, goal_id: str) -> Optional[AgentGoal]:
        """Get a goal by ID."""
        return self._goals.get(goal_id)

    def get_all_goals(self) -> List[AgentGoal]:
        """Get all goals."""
        return list(self._goals.values())

    def get_pending_goals(self) -> List[AgentGoal]:
        """Get goals that haven't started."""
        return [g for g in self._goals.values() if g.status == GoalStatus.PENDING]

    def get_active_goals(self) -> List[AgentGoal]:
        """Get goals currently in progress."""
        return [g for g in self._goals.values() if g.status == GoalStatus.IN_PROGRESS]

    def get_highest_priority_goal(self) -> Optional[AgentGoal]:
        """Get the highest priority non-terminal goal."""
        active = [g for g in self._goals.values() if not g.is_terminal()]
        if not active:
            return None
        return max(active, key=lambda g: (g.priority, -g.progress))

    def start_goal(self, goal_id: str) -> bool:
        """Mark a goal as in progress."""
        goal = self._goals.get(goal_id)
        if not goal or not goal.can_start():
            return False

        goal.status = GoalStatus.IN_PROGRESS
        self._record_progress(goal_id, 0.0, GoalStatus.IN_PROGRESS, "Started")
        logger.info(f"[{self._agent_name}] Started goal: {goal_id}")
        return True

    def update_progress(self, goal_id: str, progress: float, message: str = "") -> None:
        """Update goal progress."""
        goal = self._goals.get(goal_id)
        if not goal:
            return

        goal.progress = max(0.0, min(1.0, progress))
        self._record_progress(goal_id, goal.progress, goal.status, message)

        # Trigger callback
        if goal.on_progress:
            goal.on_progress(self._goal_history[-1])

        logger.debug(f"[{self._agent_name}] Goal {goal_id} progress: {progress:.1%}")

    def complete_goal(self, goal_id: str, message: str = "Completed") -> None:
        """Mark a goal as completed."""
        goal = self._goals.get(goal_id)
        if not goal:
            return

        goal.status = GoalStatus.COMPLETED
        goal.progress = 1.0
        goal.completed_at = datetime.now().isoformat()

        self._record_progress(goal_id, 1.0, GoalStatus.COMPLETED, message)

        # Trigger callback
        if goal.on_complete:
            try:
                goal.on_complete(goal)
            except Exception as e:
                logger.error(f"Goal completion callback failed: {e}")

        # Check if parent goal can be completed
        if goal.parent_goal:
            self._check_parent_completion(goal.parent_goal)

        logger.info(f"[{self._agent_name}] Completed goal: {goal_id}")

    def fail_goal(self, goal_id: str, reason: str) -> None:
        """Mark a goal as failed."""
        goal = self._goals.get(goal_id)
        if not goal:
            return

        goal.status = GoalStatus.FAILED
        goal.completed_at = datetime.now().isoformat()
        goal.metadata["failure_reason"] = reason

        self._record_progress(goal_id, goal.progress, GoalStatus.FAILED, reason)

        # Trigger callback
        if goal.on_fail:
            try:
                goal.on_fail(goal, reason)
            except Exception as e:
                logger.error(f"Goal failure callback failed: {e}")

        logger.warning(f"[{self._agent_name}] Failed goal: {goal_id} - {reason}")

    def block_goal(self, goal_id: str, reason: str) -> None:
        """Mark a goal as blocked."""
        goal = self._goals.get(goal_id)
        if not goal:
            return

        goal.status = GoalStatus.BLOCKED
        goal.metadata["blocked_reason"] = reason
        self._record_progress(goal_id, goal.progress, GoalStatus.BLOCKED, reason)
        logger.info(f"[{self._agent_name}] Blocked goal: {goal_id} - {reason}")

    def unblock_goal(self, goal_id: str) -> None:
        """Unblock a goal."""
        goal = self._goals.get(goal_id)
        if not goal or goal.status != GoalStatus.BLOCKED:
            return

        goal.status = GoalStatus.IN_PROGRESS
        goal.metadata.pop("blocked_reason", None)
        self._record_progress(
            goal_id, goal.progress, GoalStatus.IN_PROGRESS, "Unblocked"
        )
        logger.info(f"[{self._agent_name}] Unblocked goal: {goal_id}")

    def evaluate_progress(self, context: "AgentContext") -> Dict[str, float]:
        """
        Evaluate progress of all goals against context.

        Returns:
            Dict mapping goal_id to progress (0.0-1.0)
        """
        progress_map = {}

        for goal in self._goals.values():
            if goal.is_terminal():
                progress_map[goal.id] = (
                    1.0 if goal.status == GoalStatus.COMPLETED else 0.0
                )
                continue

            # Evaluate each criterion
            criteria_met = 0
            total_criteria = len(goal.success_criteria)

            for criterion in goal.success_criteria:
                if self._check_criterion(criterion, context):
                    criteria_met += 1

            progress = criteria_met / total_criteria if total_criteria > 0 else 0.0
            progress_map[goal.id] = progress

            # Update goal progress
            self.update_progress(goal.id, progress)

            # Auto-complete if all criteria met
            if progress >= 1.0 and goal.status != GoalStatus.COMPLETED:
                self.complete_goal(goal.id, "All success criteria met")

        return progress_map

    def derive_next_action(self, context: "AgentContext") -> Optional[Dict[str, Any]]:
        """
        Derive the next action from current goals.

        Returns:
            Dict with action details, or None if no action needed
        """
        # Get highest priority non-complete goal
        goal = self.get_highest_priority_goal()
        if not goal:
            return None

        # Start goal if pending
        if goal.status == GoalStatus.PENDING:
            self.start_goal(goal.id)

        # Find unmet criteria
        unmet_criteria = []
        for criterion in goal.success_criteria:
            if not self._check_criterion(criterion, context):
                unmet_criteria.append(criterion)

        if not unmet_criteria:
            return None

        # Map criteria to actions
        action = self._criterion_to_action(unmet_criteria[0], context)

        return {
            "goal_id": goal.id,
            "goal_description": goal.description,
            "criterion": unmet_criteria[0],
            "suggested_action": action,
            "priority": goal.priority,
            "remaining_criteria": len(unmet_criteria),
        }

    def all_goals_achieved(self) -> bool:
        """Check if all goals are achieved."""
        return all(g.status == GoalStatus.COMPLETED for g in self._goals.values())

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get summary of goal progress."""
        total = len(self._goals)
        completed = sum(
            1 for g in self._goals.values() if g.status == GoalStatus.COMPLETED
        )
        failed = sum(1 for g in self._goals.values() if g.status == GoalStatus.FAILED)
        in_progress = sum(
            1 for g in self._goals.values() if g.status == GoalStatus.IN_PROGRESS
        )

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": total - completed - failed - in_progress,
            "completion_rate": completed / total if total > 0 else 0.0,
        }

    def _check_criterion(self, criterion: str, context: "AgentContext") -> bool:
        """Check if a success criterion is met."""
        # Map criterion strings to context checks
        criterion_checks = {
            "product_data_loaded": lambda c: c.product_data is not None,
            "comparison_data_loaded": lambda c: c.comparison_data is not None,
            "analysis_complete": lambda c: c.analysis_results is not None,
            "benefits_extracted": lambda c: (
                c.analysis_results is not None
                and len(c.analysis_results.benefits or []) > 0
            ),
            "usage_extracted": lambda c: (
                c.analysis_results is not None and bool(c.analysis_results.usage)
            ),
            "questions_generated": lambda c: len(c.generated_questions or []) > 0,
            "min_questions_generated": lambda c: len(c.generated_questions or []) >= 15,
            "comparison_complete": lambda c: (
                c.analysis_results is not None and bool(c.analysis_results.comparison)
            ),
            "validation_passed": lambda c: c.is_valid,
            "no_errors": lambda c: len(c.validation_errors or []) == 0,
            "content_generated": lambda c: c.is_valid,  # Proxy for generation
        }

        check_func = criterion_checks.get(criterion)
        if check_func:
            return check_func(context)

        # Unknown criterion - assume not met
        logger.warning(f"Unknown criterion: {criterion}")
        return False

    def _criterion_to_action(self, criterion: str, context: "AgentContext") -> str:
        """Map a criterion to a suggested action."""
        action_map = {
            "product_data_loaded": "load_data",
            "comparison_data_loaded": "generate_synthetic",
            "analysis_complete": "delegate_analysis",
            "benefits_extracted": "extract_benefits",
            "usage_extracted": "extract_usage",
            "questions_generated": "generate_questions",
            "min_questions_generated": "generate_more_questions",
            "comparison_complete": "compare_products",
            "validation_passed": "validate_results",
            "no_errors": "fix_errors",
            "content_generated": "generate_content",
        }

        return action_map.get(criterion, "unknown_action")

    def _check_parent_completion(self, parent_id: str) -> None:
        """Check if parent goal can be completed after sub-goal completion."""
        parent = self._goals.get(parent_id)
        if not parent:
            return

        # Check if all sub-goals are complete
        all_sub_complete = all(
            self._goals.get(
                sg_id, AgentGoal(id="", description="", success_criteria=[])
            ).status
            == GoalStatus.COMPLETED
            for sg_id in parent.sub_goals
        )

        if all_sub_complete:
            self.complete_goal(parent_id, "All sub-goals completed")

    def _record_progress(
        self, goal_id: str, progress: float, status: GoalStatus, message: str
    ) -> None:
        """Record a progress update."""
        self._goal_history.append(
            GoalProgress(
                goal_id=goal_id, progress=progress, status=status, message=message
            )
        )

    def get_goal_history(self) -> List[GoalProgress]:
        """Get history of goal progress updates."""
        return self._goal_history.copy()


# Factory functions
def create_default_goals(agent_name: str) -> AgentGoalManager:
    """Create a goal manager with default goals for content generation."""
    manager = AgentGoalManager(agent_name)

    # Define default goals based on agent type
    if agent_name == "DataAgent":
        manager.add_goal(
            AgentGoal(
                id="load_product_data",
                description="Load and validate product data",
                success_criteria=["product_data_loaded"],
                priority=10,
            )
        )

    elif agent_name == "SyntheticDataAgent":
        manager.add_goal(
            AgentGoal(
                id="generate_comparison",
                description="Generate comparison product",
                success_criteria=["comparison_data_loaded"],
                priority=9,
            )
        )

    elif agent_name == "DelegatorAgent":
        manager.add_goal(
            AgentGoal(
                id="complete_analysis",
                description="Complete all analysis tasks",
                success_criteria=[
                    "benefits_extracted",
                    "usage_extracted",
                    "questions_generated",
                    "comparison_complete",
                    "validation_passed",
                ],
                priority=8,
            )
        )

    elif agent_name == "GenerationAgent":
        manager.add_goal(
            AgentGoal(
                id="generate_content",
                description="Generate all content pages",
                success_criteria=["content_generated"],
                priority=6,
            )
        )

    elif agent_name == "VerifierAgent":
        manager.add_goal(
            AgentGoal(
                id="verify_outputs",
                description="Verify all generated outputs",
                success_criteria=["validation_passed", "no_errors"],
                priority=5,
            )
        )

    return manager
