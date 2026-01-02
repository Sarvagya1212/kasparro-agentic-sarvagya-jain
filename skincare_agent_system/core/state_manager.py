"""
State Manager for workflow state tracking.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("StateManager")


class WorkflowPhase(str, Enum):
    IDLE = "idle"
    DATA_LOADING = "data_loading"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    COMPLETED = "completed"
    ERROR = "error"


class StateManager:
    """Manages workflow state transitions."""
    
    def __init__(self):
        self.current_phase = WorkflowPhase.IDLE
        self.phase_history: list = []
        self._is_running = False
    
    def start_workflow(self):
        """Start the workflow."""
        self._is_running = True
        self._transition_to(WorkflowPhase.DATA_LOADING)
        logger.info("Workflow started")
    
    def _transition_to(self, phase: WorkflowPhase):
        """Transition to a new phase."""
        if self.current_phase != phase:
            self.phase_history.append(self.current_phase)
            self.current_phase = phase
            logger.debug(f"Phase transition: {self.phase_history[-1]} -> {phase}")
    
    def advance_phase(self):
        """Advance to next logical phase."""
        phase_order = [
            WorkflowPhase.IDLE,
            WorkflowPhase.DATA_LOADING,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.GENERATION,
            WorkflowPhase.VALIDATION,
            WorkflowPhase.COMPLETED,
        ]
        
        try:
            current_idx = phase_order.index(self.current_phase)
            if current_idx < len(phase_order) - 1:
                self._transition_to(phase_order[current_idx + 1])
        except ValueError:
            pass
    
    def set_error(self):
        """Set error state."""
        self._transition_to(WorkflowPhase.ERROR)
        self._is_running = False
    
    def complete(self):
        """Mark workflow as complete."""
        self._transition_to(WorkflowPhase.COMPLETED)
        self._is_running = False
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def is_complete(self) -> bool:
        return self.current_phase == WorkflowPhase.COMPLETED
