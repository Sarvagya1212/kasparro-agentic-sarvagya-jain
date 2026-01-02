"""
Simplified Base Agent.
Stripped of advanced cognition for Phase 1 Simplified Version.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
)

logger = logging.getLogger("BaseAgent")


class BaseAgent(ABC):
    """
    Simplified Abstract base class for all agents.
    """

    def __init__(
        self,
        name: str,
        role: str = "Assistant",
        backstory: str = "A helpful AI assistant.",
        tools: list = None,
    ):
        self.name = name
        self.role = role
        self.backstory = backstory
        self.tools = tools or []
        self._llm = None
        self._event_bus = None

    def set_event_bus(self, event_bus: Any):
        """Set the event bus for agent-to-agent communication."""
        self._event_bus = event_bus

    def _get_llm(self):
        """Lazy load LLM client."""
        if self._llm is None and os.getenv("MISTRAL_API_KEY") is not None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                self._llm = LLMClient()
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}")
        return self._llm

    def get_agent_identity(self) -> str:
        return f"agent_{self.name}"

    def validate_instruction(self, directive: Optional[TaskDirective]) -> bool:
        if not directive:
            return True
        if directive.priority == TaskPriority.USER:
            forbidden_terms = ["ignore system", "bypass safety"]
            description = directive.description.lower()
            if any(term in description for term in forbidden_terms):
                return False
        return True

    def can_handle(self, context: AgentContext) -> bool:
        return True

    def propose(self, context: AgentContext):
        """Default proposal logic."""
        # Subclasses (Workers) override this.
        return None

    @abstractmethod
    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """Execute the agent's logic (synchronous)."""
        pass

    def create_result(
        self, status: AgentStatus, context: AgentContext, message: str = ""
    ) -> AgentResult:
        """Helper to create a standard result."""
        return AgentResult(
            agent_name=self.name, status=status, context=context, message=message
        )

    # Stubs for compatibility if needed
    def set_memory(self, memory: Any):
        pass

    def set_goal_manager(self, gm: Any):
        pass
