"""
Base Agent with Autonomy Support.
Agents can now propose actions based on context assessment.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
)
from .proposals import AgentProposal

logger = logging.getLogger("BaseAgent")


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Supports:
    - Roles and Backstories (persona engineering)
    - Instruction Hierarchy (SYSTEM > USER)
    - Agent Autonomy (can_handle, propose)
    """

    def __init__(
        self,
        name: str,
        role: str = "Assistant",
        backstory: str = "A helpful AI assistant.",
    ):
        self.name = name
        self.role = role
        self.backstory = backstory
        self.system_prompt = f"Role: {role}\nBackstory: {backstory}\n"

    def validate_instruction(self, directive: Optional[TaskDirective]) -> bool:
        """
        Enforce Instruction Hierarchy: SYSTEM > USER.
        If a user directive conflicts with system safety, reject it.
        """
        if not directive:
            return True

        logger.info(
            f"[{self.name}] Validating directive: {directive.description} "
            f"(Priority: {directive.priority.value})"
        )

        if directive.priority == TaskPriority.USER:
            forbidden_terms = ["ignore system", "bypass safety"]
            if any(term in directive.description.lower() for term in forbidden_terms):
                logger.warning(
                    f"[{self.name}] SECURITY: User directive attempted to bypass system."
                )
                return False

        return True

    # ==================== AUTONOMY METHODS ====================

    def can_handle(self, context: AgentContext) -> bool:
        """
        Check if this agent can handle the current context.
        Override in subclasses to implement specific logic.

        Returns:
            True if agent's preconditions are met
        """
        # Default: always can handle (override in subclasses)
        return True

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """
        Propose an action based on context assessment.
        This is the core of agent autonomy - agents decide what they can do.

        Returns:
            AgentProposal with confidence score, or None if nothing to propose
        """
        # Default implementation - override in subclasses
        can_do = self.can_handle(context)
        if not can_do:
            return None

        return AgentProposal(
            agent_name=self.name,
            action="execute",
            confidence=0.5,  # Default confidence
            reason="Default proposal - override in subclass",
            preconditions_met=can_do,
            priority=0
        )

    def get_confidence(self, context: AgentContext) -> float:
        """
        Calculate confidence score for handling current context.
        Higher confidence = more suitable for this task.

        Returns:
            Float between 0.0 and 1.0
        """
        # Default: medium confidence
        return 0.5

    # ==================== CORE METHODS ====================

    @abstractmethod
    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """Execute the agent's logic."""
        pass

    def create_result(
        self, status: AgentStatus, context: AgentContext, message: str = ""
    ) -> AgentResult:
        """Helper to create a standard result."""
        return AgentResult(
            agent_name=self.name, status=status, context=context, message=message
        )
