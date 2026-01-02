"""
Advanced Reasoning: Chain of Thought (CoT) and ReAct patterns.
Now with LLM-powered reasoning when API key is available.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.core.models import AgentContext

logger = logging.getLogger("Reasoning")

# Check if LLM is available
# Check if LLM is available (Checked lazily in classes now)
# LLM_ENABLED = os.getenv("GEMINI_API_KEY") is not None


class ThoughtType(Enum):
    """Types of thoughts in a reasoning chain."""

    OBSERVATION = "observation"
    REASONING = "reasoning"
    DECISION = "decision"
    ACTION = "action"
    REFLECTION = "reflection"


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
        return self.add_thought(ThoughtType.OBSERVATION, observation, confidence)

    def reason(self, reasoning: str, confidence: float = 1.0):
        return self.add_thought(ThoughtType.REASONING, reasoning, confidence)

    def decide(self, decision: str, confidence: float = 1.0):
        self.final_decision = decision
        return self.add_thought(ThoughtType.DECISION, decision, confidence)

    def act(self, action: str, confidence: float = 1.0):
        return self.add_thought(ThoughtType.ACTION, action, confidence)

    def reflect(self, reflection: str, confidence: float = 1.0):
        return self.add_thought(ThoughtType.REFLECTION, reflection, confidence)

    def to_log(self) -> List[str]:
        return [str(step) for step in self.steps]


class ReActReasoner:
    """
    ReAct (Reason + Act) pattern for agent reasoning.
    Uses LLM when available, falls back to heuristics.
    """

    def __init__(self):
        self.chains: List[ReasoningChain] = []
        self._llm = None

    def _get_llm(self):
        """Lazy load LLM client."""
        if self._llm is None and os.getenv("MISTRAL_API_KEY") is not None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                self._llm = LLMClient()
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}")
        return self._llm

    def start_chain(self, goal: str) -> ReasoningChain:
        """Start a new reasoning chain for a goal."""
        chain = ReasoningChain(goal=goal)
        self.chains.append(chain)
        logger.info(f"Started reasoning chain for goal: {goal}")
        return chain

    def reason_about_context(
        self, chain: ReasoningChain, context: "AgentContext"
    ) -> ReasoningChain:
        """Apply ReAct pattern to analyze context."""
        llm = self._get_llm()
        if llm:
            return self._reason_with_llm(chain, context, llm)
        else:
            return self._reason_heuristic(chain, context)

    def _reason_with_llm(
        self, chain: ReasoningChain, context: "AgentContext", llm
    ) -> ReasoningChain:
        """Use LLM for ReAct reasoning."""
        prompt = f"""You are an AI agent using the ReAct pattern (Reason + Act).

Goal: {chain.goal}

Current Context State:
- Product Data: {context.product_data.name if context.product_data else 'None'}
- Comparison Data: {context.comparison_data.name if context.comparison_data else 'None'}
- Analysis Results: {'Yes' if context.analysis_results else 'No'}
- Is Validated: {'Yes' if context.is_valid else 'No'}
- Generated Questions: {len(context.generated_questions) if context.generated_questions else 0}

Available Agents:
1. DataAgent - Loads product data
2. SyntheticDataAgent - Creates comparison product
3. DelegatorAgent - Coordinates analysis workers
4. GenerationAgent - Creates JSON outputs
5. VerifierAgent - Verifies outputs

Think step by step:

Respond with JSON:
{{
    "observation": "What I observe about the current state",
    "reasoning": "Why I think this based on the observation",
    "decision": "What action to take next",
    "next_agent": "Which agent should act",
    "confidence": 0.0-1.0
}}"""

        try:
            response = llm.generate_json(prompt)

            observation = response.get("observation", "Context analyzed")
            reasoning = response.get("reasoning", "Proceeding based on state")
            decision = response.get("decision", "Continue workflow")
            next_agent = response.get("next_agent", "Unknown")
            confidence = response.get("confidence", 0.8)

            chain.observe(f"[LLM] {observation}", confidence)
            chain.reason(f"[LLM] {reasoning}", confidence)
            chain.decide(f"{next_agent} should {decision}", confidence)

            logger.info(f"LLM reasoning: {observation} -> {decision}")
            return chain

        except Exception as e:
            logger.warning(f"LLM reasoning failed, using heuristic: {e}")
            return self._reason_heuristic(chain, context)

    def _reason_heuristic(
        self, chain: ReasoningChain, context: "AgentContext"
    ) -> ReasoningChain:
        """Fallback heuristic reasoning."""
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
        return self.chains.copy()


@dataclass
class SubTask:
    """A sub-task in hierarchical decomposition."""

    id: str
    description: str
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    assigned_agent: Optional[str] = None


class TaskDecomposer:
    """
    Hierarchical Task Network (HTN) decomposition.
    Uses LLM for dynamic decomposition when available.
    """

    def __init__(self):
        self.task_tree: Dict[str, SubTask] = {}
        self._llm = None

    def _get_llm(self):
        if self._llm is None and os.getenv("MISTRAL_API_KEY") is not None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                self._llm = LLMClient()
            except Exception:
                pass
        return self._llm

    def decompose_goal(self, goal: str) -> List[SubTask]:
        """Decompose a high-level goal into sub-tasks."""
        llm = self._get_llm()
        if llm and "content" not in goal.lower():
            return self._decompose_with_llm(goal, llm)

        # Use predefined decomposition for content generation
        if "content" in goal.lower() or "generate" in goal.lower():
            sub_tasks = self._decompose_content_generation()
        else:
            sub_tasks = [SubTask(id="t1", description=goal)]

        for task in sub_tasks:
            self.task_tree[task.id] = task

        logger.info(f"Decomposed '{goal}' into {len(sub_tasks)} sub-tasks")
        return sub_tasks

    def _decompose_with_llm(self, goal: str, llm) -> List[SubTask]:
        """Use LLM to decompose arbitrary goals."""
        prompt = f"""Break down this goal into 3-6 sub-tasks:

Goal: {goal}

Respond with JSON array:
[
    {{"id": "t1", "description": "First task", "dependencies": [], "assigned_agent": "AgentName"}},
    {{"id": "t2", "description": "Second task", "dependencies": ["t1"], "assigned_agent": "AgentName"}}
]

Available agents: DataAgent, SyntheticDataAgent, DelegatorAgent, GenerationAgent, VerifierAgent"""

        try:
            tasks_data = llm.generate_json(prompt)
            if isinstance(tasks_data, list):
                sub_tasks = [
                    SubTask(
                        id=t.get("id", f"t{i}"),
                        description=t.get("description", ""),
                        dependencies=t.get("dependencies", []),
                        assigned_agent=t.get("assigned_agent"),
                    )
                    for i, t in enumerate(tasks_data)
                ]
                for task in sub_tasks:
                    self.task_tree[task.id] = task
                return sub_tasks
        except Exception as e:
            logger.warning(f"LLM decomposition failed: {e}")

        return [SubTask(id="t1", description=goal)]

    def _decompose_content_generation(self) -> List[SubTask]:
        """Decompose content generation goal."""
        return [
            SubTask(
                id="t1", description="Load product data", assigned_agent="DataAgent"
            ),
            SubTask(
                id="t2",
                description="Generate comparison product",
                dependencies=["t1"],
                assigned_agent="SyntheticDataAgent",
            ),
            SubTask(
                id="t3",
                description="Run analysis (benefits, usage, questions)",
                dependencies=["t1", "t2"],
                assigned_agent="DelegatorAgent",
            ),
            SubTask(
                id="t4",
                description="Validate analysis results",
                dependencies=["t3"],
                assigned_agent="ValidationWorker",
            ),
            SubTask(
                id="t5",
                description="Generate content pages (FAQ, Product, Comparison)",
                dependencies=["t4"],
                assigned_agent="GenerationAgent",
            ),
            SubTask(
                id="t6",
                description="Verify outputs for quality and safety",
                dependencies=["t5"],
                assigned_agent="VerifierAgent",
            ),
        ]

    def get_next_executable(self) -> Optional[SubTask]:
        for task in self.task_tree.values():
            if task.status == "pending":
                deps_met = all(
                    self.task_tree.get(dep, SubTask(id="", description="")).status
                    == "complete"
                    for dep in task.dependencies
                )
                if deps_met or not task.dependencies:
                    return task
        return None

    def mark_complete(self, task_id: str):
        if task_id in self.task_tree:
            self.task_tree[task_id].status = "complete"
            logger.info(f"Task {task_id} marked complete")

    def get_task_tree(self) -> Dict[str, SubTask]:
        return self.task_tree.copy()


class ChainOfThought:
    """Chain of Thought (CoT) prompting helper with LLM support."""

    _llm = None

    @classmethod
    def _get_llm(cls):
        if cls._llm is None and os.getenv("MISTRAL_API_KEY") is not None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                cls._llm = LLMClient()
            except Exception:
                pass
        return cls._llm

    @classmethod
    def generate_reasoning(
        cls, agent_name: str, context: "AgentContext", action: str
    ) -> List[str]:
        """Generate CoT reasoning for an action."""
        llm = cls._get_llm()
        if llm:
            return cls._generate_with_llm(agent_name, context, action, llm)
        return cls._generate_heuristic(context, action)

    @classmethod
    def _generate_with_llm(
        cls, agent_name: str, context: "AgentContext", action: str, llm
    ) -> List[str]:
        """Use LLM for Chain of Thought."""
        prompt = f"""You are {agent_name} about to {action}.

Context:
- Product: {context.product_data.name if context.product_data else 'None'}
- Comparison: {context.comparison_data.name if context.comparison_data else 'None'}
- Validated: {context.is_valid}

Generate 3-4 reasoning steps explaining your thought process.

Respond with JSON:
{{"thoughts": ["First thought...", "Second thought...", "Therefore I will..."]}}"""

        try:
            response = llm.generate_json(prompt)
            thoughts = response.get("thoughts", [])
            if thoughts:
                return [f"[LLM] {t}" for t in thoughts]
        except Exception as e:
            logger.warning(f"LLM CoT failed: {e}")

        return cls._generate_heuristic(context, action)

    @classmethod
    def _generate_heuristic(cls, context: "AgentContext", action: str) -> List[str]:
        """Fallback heuristic CoT."""
        thoughts = []

        if context.product_data:
            thoughts.append(f"I see product '{context.product_data.name}' is loaded")
        else:
            thoughts.append("I observe no product data in context")

        if context.comparison_data:
            thoughts.append(
                f"Comparison product '{context.comparison_data.name}' exists"
            )

        if context.analysis_results:
            thoughts.append(
                f"Analysis has {len(context.analysis_results.benefits)} benefits"
            )

        if context.is_valid:
            thoughts.append("Context has been validated")

        thoughts.append(f"Therefore, I will {action}")

        return thoughts


@dataclass
class ToTNode:
    """Node in Tree of Thoughts."""

    content: str
    parent: Optional["ToTNode"] = None
    children: List["ToTNode"] = field(default_factory=list)
    score: float = 0.0
    depth: int = 0
    path: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.parent:
            self.path = self.parent.path + [self.content]
            self.depth = self.parent.depth + 1
        else:
            self.path = [self.content]


class TreeOfThoughts:
    """
    Tree of Thoughts (ToT) reasoning.
    Explores multiple reasoning paths using BFS/DFS search.
    """

    def __init__(self, max_depth: int = 3, branching_factor: int = 3):
        self.max_depth = max_depth
        self.branching_factor = branching_factor
        self._llm = None

    def _get_llm(self):
        if self._llm is None and os.getenv("MISTRAL_API_KEY") is not None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                self._llm = LLMClient()
            except Exception:
                pass
        return self._llm

    def solve(self, goal: str, initial_state: str, strategy: str = "bfs") -> List[str]:
        """
        Solve a problem using ToT search.
        Returns the best reasoning path found.
        """
        llm = self._get_llm()
        if not llm:
            logger.warning("ToT requires LLM. Falling back to linear CoT.")
            return [
                initial_state,
                "LLM unavailable for Tree Search",
                "Action based on heuristic",
            ]

        root = ToTNode(content=initial_state)
        best_node = root

        # Frontier for search
        frontier = [root]

        while frontier:
            # Expand next node
            if strategy == "dfs":
                current_node = frontier.pop()  # LIFO
            else:  # bfs
                current_node = frontier.pop(0)  # FIFO

            if current_node.depth >= self.max_depth:
                if current_node.score > best_node.score:
                    best_node = current_node
                continue

            # Generate thoughts
            thoughts = self._generate_thoughts(current_node, goal, llm)

            # Evaluate thoughts
            scored_thoughts = self._evaluate_thoughts(current_node, thoughts, goal, llm)

            for thought_content, score in scored_thoughts:
                child = ToTNode(
                    content=thought_content, parent=current_node, score=score
                )
                current_node.children.append(child)

                # Pruning: Only add promising nodes (score > 0.5)
                if score > 0.5:
                    frontier.append(child)

                # Update best
                if score > best_node.score:
                    best_node = child

        logger.info(f"ToT Search Complete. Best Score: {best_node.score}")
        return best_node.path

    def _generate_thoughts(self, node: ToTNode, goal: str, llm) -> List[str]:
        """Generate possible next thoughts."""
        context_path = " -> ".join(node.path[-2:])  # Last 2 steps context
        prompt = f"""Problem: {goal}
Current Reasoning Path: ... {context_path}

Generate {self.branching_factor} Distinct, alternative next reasoning steps or actions.
Be creative and diverse.

Respond with JSON:
{{"thoughts": ["Thought A...", "Thought B...", "Thought C..."]}}"""

        try:
            response = llm.generate_json(prompt)
            return response.get("thoughts", [])[: self.branching_factor]
        except Exception as e:
            logger.warning(f"ToT Generation failed: {e}")
            return []

    def _evaluate_thoughts(
        self, node: ToTNode, thoughts: List[str], goal: str, llm
    ) -> List[tuple]:
        """Score thoughts (0.0 - 1.0) based on contribution to goal."""
        if not thoughts:
            return []

        prompt = f"""Problem: {goal}
Current State: {node.content}

Evaluate these possible next steps. Assign a score (0.0 to 1.0) for how likely each step leads to a successful solution.

Candidates:
{json.dumps(thoughts, indent=2)}

Respond with JSON:
{{"scores": [0.9, 0.4, 0.1]}} (corresponding to the input order)"""

        try:
            response = llm.generate_json(prompt)
            scores = response.get("scores", [])
            # Pad or truncate
            result = []
            for i, thought in enumerate(thoughts):
                score = scores[i] if i < len(scores) else 0.5
                result.append((thought, float(score)))
            return result
        except Exception as e:
            logger.warning(f"ToT Evaluation failed: {e}")
            return [(t, 0.5) for t in thoughts]
