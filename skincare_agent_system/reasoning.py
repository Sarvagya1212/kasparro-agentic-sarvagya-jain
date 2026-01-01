"""
Advanced Reasoning: Chain of Thought (CoT) and ReAct patterns.
Enables agents to "think out loud" and decompose complex goals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AgentContext

logger = logging.getLogger("Reasoning")


class ThoughtType(Enum):
    """Types of thoughts in a reasoning chain."""
    OBSERVATION = "observation"  # What we see in context
    REASONING = "reasoning"      # Why we think something
    DECISION = "decision"        # What we decide to do
    ACTION = "action"           # What we will execute
    REFLECTION = "reflection"   # Self-critique


@dataclass
class ThoughtStep:
    """Single step in Chain of Thought reasoning."""
    type: ThoughtType
    content: str
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __repr__(self):
        return f"[{self.type.value.upper()}] {self.content}"


@dataclass
class ReasoningChain:
    """Complete reasoning chain for a goal."""
    goal: str
    steps: List[ThoughtStep] = field(default_factory=list)
    final_decision: Optional[str] = None
    success: bool = False

    def add_thought(self, type: ThoughtType, content: str, confidence: float = 1.0):
        """Add a thought to the chain."""
        step = ThoughtStep(type=type, content=content, confidence=confidence)
        self.steps.append(step)
        logger.debug(f"Thought: {step}")
        return step

    def observe(self, observation: str, confidence: float = 1.0):
        """Add an observation."""
        return self.add_thought(ThoughtType.OBSERVATION, observation, confidence)

    def reason(self, reasoning: str, confidence: float = 1.0):
        """Add reasoning."""
        return self.add_thought(ThoughtType.REASONING, reasoning, confidence)

    def decide(self, decision: str, confidence: float = 1.0):
        """Add a decision."""
        self.final_decision = decision
        return self.add_thought(ThoughtType.DECISION, decision, confidence)

    def act(self, action: str, confidence: float = 1.0):
        """Add an action."""
        return self.add_thought(ThoughtType.ACTION, action, confidence)

    def reflect(self, reflection: str, confidence: float = 1.0):
        """Add self-reflection."""
        return self.add_thought(ThoughtType.REFLECTION, reflection, confidence)

    def to_log(self) -> List[str]:
        """Convert to log-friendly format."""
        return [str(step) for step in self.steps]


class ReActReasoner:
    """
    ReAct (Reason + Act) pattern for agent reasoning.
    Alternates between thinking and acting.

    Pattern:
    1. Observe context
    2. Reason about what to do
    3. Decide on action
    4. Act
    5. Reflect on outcome
    """

    def __init__(self):
        self.chains: List[ReasoningChain] = []

    def start_chain(self, goal: str) -> ReasoningChain:
        """Start a new reasoning chain for a goal."""
        chain = ReasoningChain(goal=goal)
        self.chains.append(chain)
        logger.info(f"Started reasoning chain for goal: {goal}")
        return chain

    def reason_about_context(
        self,
        chain: ReasoningChain,
        context: "AgentContext"
    ) -> ReasoningChain:
        """Apply ReAct pattern to analyze context."""
        # Observation phase
        if context.product_data is None:
            chain.observe("No product data in context")
            chain.reason("Data must be loaded before any analysis")
            chain.decide("DataAgent should load product data")
        elif context.comparison_data is None:
            chain.observe("Product data exists but no comparison data")
            chain.reason("Comparison page requires a second product")
            chain.decide("SyntheticDataAgent should generate competitor")
        elif context.analysis_results is None:
            chain.observe("Data ready but no analysis performed")
            chain.reason("Analysis must complete before generation")
            chain.decide("DelegatorAgent should run analysis workers")
        elif not context.is_valid:
            chain.observe("Analysis exists but not validated")
            chain.reason("Validation required before content generation")
            chain.decide("ValidationWorker should validate results")
        elif context.is_valid:
            chain.observe("Context validated and ready")
            chain.reason("All prerequisites met for generation")
            chain.decide("GenerationAgent should create outputs")

        return chain

    def get_all_chains(self) -> List[ReasoningChain]:
        """Get all reasoning chains."""
        return self.chains.copy()


@dataclass
class SubTask:
    """A sub-task in hierarchical decomposition."""
    id: str
    description: str
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, complete
    assigned_agent: Optional[str] = None


class TaskDecomposer:
    """
    Hierarchical Task Network (HTN) decomposition.
    Breaks high-level goals into executable sub-tasks.
    """

    def __init__(self):
        self.task_tree: Dict[str, SubTask] = {}

    def decompose_goal(self, goal: str) -> List[SubTask]:
        """
        Decompose a high-level goal into sub-tasks.

        Example:
        "Generate content pages" ->
            1. Load product data
            2. Generate comparison product
            3. Run analysis
            4. Validate results
            5. Generate outputs
            6. Verify outputs
        """
        sub_tasks = []

        if "content" in goal.lower() or "generate" in goal.lower():
            sub_tasks = self._decompose_content_generation()
        else:
            # Default single task
            sub_tasks = [SubTask(id="t1", description=goal)]

        # Store in tree
        for task in sub_tasks:
            self.task_tree[task.id] = task

        logger.info(f"Decomposed '{goal}' into {len(sub_tasks)} sub-tasks")
        return sub_tasks

    def _decompose_content_generation(self) -> List[SubTask]:
        """Decompose content generation goal."""
        return [
            SubTask(
                id="t1",
                description="Load product data",
                assigned_agent="DataAgent"
            ),
            SubTask(
                id="t2",
                description="Generate comparison product",
                dependencies=["t1"],
                assigned_agent="SyntheticDataAgent"
            ),
            SubTask(
                id="t3",
                description="Run analysis (benefits, usage, questions)",
                dependencies=["t1", "t2"],
                assigned_agent="DelegatorAgent"
            ),
            SubTask(
                id="t4",
                description="Validate analysis results",
                dependencies=["t3"],
                assigned_agent="ValidationWorker"
            ),
            SubTask(
                id="t5",
                description="Generate content pages (FAQ, Product, Comparison)",
                dependencies=["t4"],
                assigned_agent="GenerationAgent"
            ),
            SubTask(
                id="t6",
                description="Verify outputs for quality and safety",
                dependencies=["t5"],
                assigned_agent="VerifierAgent"
            ),
        ]

    def get_next_executable(self) -> Optional[SubTask]:
        """Get next task that can be executed (dependencies met)."""
        for task in self.task_tree.values():
            if task.status == "pending":
                deps_met = all(
                    self.task_tree.get(dep, SubTask(id="", description="")).status == "complete"
                    for dep in task.dependencies
                )
                if deps_met or not task.dependencies:
                    return task
        return None

    def mark_complete(self, task_id: str):
        """Mark a task as complete."""
        if task_id in self.task_tree:
            self.task_tree[task_id].status = "complete"
            logger.info(f"Task {task_id} marked complete")

    def get_task_tree(self) -> Dict[str, SubTask]:
        """Get full task tree."""
        return self.task_tree.copy()


class ChainOfThought:
    """
    Chain of Thought (CoT) prompting helper.
    Helps agents verbalize their reasoning.
    """

    @staticmethod
    def generate_reasoning(
        agent_name: str,
        context: "AgentContext",
        action: str
    ) -> List[str]:
        """
        Generate CoT reasoning for an action.

        Returns list of thought strings that explain the reasoning.
        """
        thoughts = []

        # Context observation
        if context.product_data:
            thoughts.append(f"I see product '{context.product_data.name}' is loaded")
        else:
            thoughts.append("I observe no product data in context")

        if context.comparison_data:
            thoughts.append(f"Comparison product '{context.comparison_data.name}' exists")

        if context.analysis_results:
            thoughts.append(f"Analysis has {len(context.analysis_results.benefits)} benefits")

        if context.is_valid:
            thoughts.append("Context has been validated")

        # Action reasoning
        thoughts.append(f"Therefore, I will {action}")

        return thoughts
