"""
State Manager: Structured State Space for workflow tracking.
Maintains workflow status, available actions, and outcomes.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("StateManager")


class WorkflowStatus(Enum):
    """Workflow lifecycle states."""
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    AWAITING_INPUT = "AWAITING_INPUT"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


@dataclass
class StateSpace:
    """
    Structured State Space for tracking system state.
    Provides clear visibility into current situation, available actions, and outcomes.
    """

    workflow_status: WorkflowStatus = WorkflowStatus.IDLE
    current_agent: Optional[str] = None
    current_phase: str = "initialization"
    available_actions: List[str] = field(default_factory=list)
    outcomes: Dict[str, Any] = field(default_factory=dict)
    transition_history: List[Dict[str, Any]] = field(default_factory=list)

    # Domain-specific state tracking
    product_id: Optional[str] = None
    comparison_product_id: Optional[str] = None
    generation_status: Dict[str, bool] = field(default_factory=dict)

    def transition(self, action: str, agent: str, outcome: Any = None) -> bool:
        """
        Execute a state transition.

        Args:
            action: The action being taken
            agent: The agent performing the action
            outcome: Optional outcome data

        Returns:
            True if transition was valid
        """
        if action not in self.available_actions and self.available_actions:
            logger.warning(
                f"Invalid action '{action}'. Available: {self.available_actions}"
            )
            return False

        # Record transition
        transition_record = {
            "timestamp": datetime.now().isoformat(),
            "from_status": self.workflow_status.value,
            "action": action,
            "agent": agent,
            "outcome": outcome,
        }
        self.transition_history.append(transition_record)

        # Update state
        self.current_agent = agent
        self.outcomes[agent] = outcome

        logger.info(f"State transition: {action} by {agent}")
        return True

    def set_phase(self, phase: str, available_actions: List[str]):
        """Update current phase and available actions."""
        self.current_phase = phase
        self.available_actions = available_actions
        logger.info(f"Phase: {phase}, Actions: {available_actions}")

    def mark_complete(self, output_type: str):
        """Mark an output as generated."""
        self.generation_status[output_type] = True

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current state."""
        return {
            "status": self.workflow_status.value,
            "phase": self.current_phase,
            "current_agent": self.current_agent,
            "available_actions": self.available_actions,
            "outputs_generated": list(self.generation_status.keys()),
            "transition_count": len(self.transition_history),
        }


class StateManager:
    """
    Manages StateSpace lifecycle and persistence.
    """

    def __init__(self):
        self.state_space = StateSpace()
        self._checkpoints: List[StateSpace] = []

    def get_state(self) -> StateSpace:
        """Get current state space."""
        return self.state_space

    def reset(self):
        """Reset to initial state."""
        self.state_space = StateSpace()
        logger.info("State reset to IDLE")

    def checkpoint(self):
        """Save current state as checkpoint."""
        import copy
        self._checkpoints.append(copy.deepcopy(self.state_space))
        logger.info(f"Checkpoint saved ({len(self._checkpoints)} total)")

    def rollback(self) -> bool:
        """Rollback to last checkpoint."""
        if not self._checkpoints:
            logger.warning("No checkpoints to rollback to")
            return False

        self.state_space = self._checkpoints.pop()
        logger.info("Rolled back to previous checkpoint")
        return True

    def start_workflow(self):
        """Initialize workflow state."""
        self.state_space.workflow_status = WorkflowStatus.PROCESSING
        self.state_space.set_phase(
            "data_loading",
            ["load_data", "generate_synthetic", "skip_to_analysis"]
        )

    def complete_workflow(self):
        """Mark workflow as complete."""
        self.state_space.workflow_status = WorkflowStatus.COMPLETE
        self.state_space.available_actions = []

    def mark_error(self, error_msg: str):
        """Mark workflow as errored."""
        self.state_space.workflow_status = WorkflowStatus.ERROR
        self.state_space.outcomes["error"] = error_msg
