import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Type

from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    SystemState,
    TaskDirective,
    TaskPriority,
)

logger = logging.getLogger("BaseAgent")


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Now supports Roles, Backstories, and Hierarchy Enforcement.
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
        If a user directive conflicts with system safety/role definitions, reject it.
        """
        if not directive:
            return True

        # Simulation of hierarchy check (in a real LLM system, this would be part of the prompt)
        logger.info(
            f"[{self.name}] Validating directive: {directive.description} (Priority: {directive.priority.value})"
        )

        if directive.priority == TaskPriority.USER:
            # Simple keyword safeguard simulation
            forbidden_terms = ["ignore system", "bypass safety"]
            if any(term in directive.description.lower() for term in forbidden_terms):
                logger.warning(
                    f"[{self.name}] SECURITY ALERT: User directive attempted to bypass system prompts."
                )
                return False

        return True

    @abstractmethod
    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """Execute the agent's logic. Now accepts an optional directive."""
        pass

    def create_result(
        self, status: AgentStatus, context: AgentContext, message: str = ""
    ) -> AgentResult:
        """Helper to create a standard result."""
        return AgentResult(
            agent_name=self.name, status=status, context=context, message=message
        )
