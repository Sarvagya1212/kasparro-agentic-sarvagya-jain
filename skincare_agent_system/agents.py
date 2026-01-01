"""
Base Agent with Autonomy Support.
Agents can propose actions, reason with CoT, and self-reflect.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
)
from .proposals import AgentProposal
from .reasoning import ChainOfThought, ReActReasoner, ReasoningChain, ThoughtType
from .reflection import ReflectionResult, SelfReflector

logger = logging.getLogger("BaseAgent")


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Supports:
    - Roles and Backstories (persona engineering)
    - Instruction Hierarchy (SYSTEM > USER)
    - Agent Autonomy (can_handle, propose)
    - Chain of Thought reasoning
    - Self-reflection capability
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

        # Advanced cognition capabilities
        self.reasoner = ReActReasoner()
        self.reflector = SelfReflector()
        self._reasoning_chain: Optional[ReasoningChain] = None

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

    # ==================== REASONING METHODS ====================

    def start_reasoning(self, goal: str) -> ReasoningChain:
        """Start a Chain of Thought reasoning chain."""
        self._reasoning_chain = self.reasoner.start_chain(goal)
        return self._reasoning_chain

    def think(self, thought: str, thought_type: ThoughtType = ThoughtType.REASONING):
        """Add a thought to the current reasoning chain."""
        if self._reasoning_chain:
            self._reasoning_chain.add_thought(thought_type, thought)

    def log_reasoning(self, context: AgentContext):
        """Log the reasoning chain to context."""
        if self._reasoning_chain:
            for step in self._reasoning_chain.steps:
                context.log_decision(self.name, f"[{step.type.value.upper()}] {step.content}")

    def generate_cot_reasoning(self, context: AgentContext, action: str) -> List[str]:
        """Generate Chain of Thought reasoning for an action."""
        return ChainOfThought.generate_reasoning(self.name, context, action)

    # ==================== REFLECTION METHODS ====================

    def reflect(self, output: AgentResult, context: AgentContext) -> ReflectionResult:
        """Perform self-reflection on output."""
        return self.reflector.reflect_on_output(self.name, output, context)

    def run_with_reflection(
        self,
        context: AgentContext,
        directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """
        Run with self-reflection loop.
        1. Execute
        2. Reflect
        3. Improve if needed
        """
        # Step 1: Execute
        result = self.run(context, directive)

        # Step 2: Self-reflect
        reflection = self.reflect(result, context)

        # Log reflection
        context.log_decision(
            self.name,
            f"[REFLECTION] {'PASS' if reflection.is_acceptable else 'FAIL'} "
            f"(confidence: {reflection.confidence:.2f})"
        )

        # Step 3: Log suggestions if any
        if reflection.suggestions:
            for suggestion in reflection.suggestions:
                context.log_decision(self.name, f"[SUGGESTION] {suggestion}")

        return result

    # ==================== AUTONOMY METHODS ====================

    def can_handle(self, context: AgentContext) -> bool:
        """
        Check if this agent can handle the current context.
        Override in subclasses to implement specific logic.
        """
        return True

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """
        Propose an action based on context assessment.
        This is the core of agent autonomy.
        """
        can_do = self.can_handle(context)
        if not can_do:
            return None

        return AgentProposal(
            agent_name=self.name,
            action="execute",
            confidence=0.5,
            reason="Default proposal - override in subclass",
            preconditions_met=can_do,
            priority=0
        )

    def get_confidence(self, context: AgentContext) -> float:
        """Calculate confidence score for handling current context."""
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
