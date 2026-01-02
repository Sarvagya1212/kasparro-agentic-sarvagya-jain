"""
LLM-powered reasoning engine for agent decision-making.
Replaces hardcoded can_handle() checks with actual reasoning.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Result of LLM reasoning about an action"""

    should_act: bool
    confidence: float  # 0.0-1.0
    reasoning: str
    complexity: str  # low, medium, high
    prerequisites_met: bool
    risks: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReasoningEngine:
    """
    Provides LLM-based reasoning capabilities to agents.
    Uses your existing provider system. Fails safe if unavailable.
    """

    def __init__(self, provider=None):
        if provider is None:
            from ..infrastructure.providers import get_provider

            self.provider = get_provider()
        else:
            self.provider = provider

        logger.info(f"ReasoningEngine initialized with provider: {self.provider.name}")

    def reason_about_action(
        self,
        agent_name: str,
        task_description: str,
        context_summary: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> ReasoningResult:
        """
        Have LLM reason about whether agent should act.

        Args:
            agent_name: Name of the agent
            task_description: What the agent is supposed to do
            context_summary: Current context state
            constraints: Task constraints and requirements

        Returns:
            ReasoningResult with decision and reasoning chain
        """
        prompt = self._build_reasoning_prompt(
            agent_name, task_description, context_summary, constraints
        )

        try:
            # Use provider's generate for structured output
            response_text = self.provider.generate(prompt, temperature=0.3)
            result = self._parse_reasoning_response(response_text)

            logger.info(
                f"{agent_name} reasoning: "
                f"confidence={result.confidence:.2f}, "
                f"should_act={result.should_act}"
            )

            return result

        except Exception as e:
            logger.warning(
                f"LLM reasoning failed for {agent_name}: {e}, " f"using heuristic"
            )
            return self._fallback_reasoning(
                agent_name, context_summary, task_description
            )

    def _build_reasoning_prompt(
        self,
        agent_name: str,
        task: str,
        context: Dict,
        constraints: Optional[Dict],
    ) -> str:
        """Build chain-of-thought reasoning prompt"""

        # Format context nicely
        context_str = "\n".join([f"  - {k}: {v}" for k, v in context.items()])
        constraints_str = "\n".join(
            [f"  - {k}: {v}" for k, v in (constraints or {}).items()]
        )

        return f"""You are {agent_name}, an autonomous AI agent in a multi-agent system.

Your task: {task}

Current context:
{context_str}

Constraints:
{constraints_str if constraints else "  - None specified"}

Perform chain-of-thought reasoning to decide whether you should act:

Step 1 - Prerequisites Check:
- Do I have all required data to complete this task?
- Are there dependencies that must be satisfied first?

Step 2 - Capability Assessment:
- Am I the right agent for this task?
- Is this task within my specialization?

Step 3 - Complexity Analysis:
- How difficult is this task given the current context?
- What challenges might I face?

Step 4 - Risk Assessment:
- What could go wrong if I act now?
- Are there any blocking conditions?

Step 5 - Confidence Calculation:
- Based on all factors above, how confident am I (0.0-1.0)?
- Should I act now or wait?

Respond ONLY with valid JSON (no markdown):
{{
    "should_act": true,
    "confidence": 0.85,
    "reasoning": "detailed step-by-step explanation of your decision",
    "complexity": "medium",
    "prerequisites_met": true,
    "risks": ["risk 1", "risk 2"],
    "alternatives": ["alternative approach"]
}}"""

    def _parse_reasoning_response(self, response: str) -> ReasoningResult:
        """Parse and validate LLM reasoning response"""
        # Clean markdown if present
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {cleaned[:200]}")
            raise ValueError(f"Invalid JSON response: {e}")

        # Validate required fields
        required = ["should_act", "confidence", "reasoning"]
        missing = [f for f in required if f not in parsed]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Validate types
        if not isinstance(parsed["should_act"], bool):
            raise ValueError("should_act must be boolean")

        if not isinstance(parsed["confidence"], (int, float)):
            raise ValueError("confidence must be numeric")

        confidence = float(parsed["confidence"])
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

        # Build result
        return ReasoningResult(
            should_act=parsed["should_act"],
            confidence=confidence,
            reasoning=parsed["reasoning"],
            complexity=parsed.get("complexity", "medium"),
            prerequisites_met=parsed.get("prerequisites_met", True),
            risks=parsed.get("risks", []),
            alternatives=parsed.get("alternatives", []),
            metadata=parsed,
        )

    def _fallback_reasoning(
        self, agent_name: str, context: Dict, task: str
    ) -> ReasoningResult:
        """Return safe failure state when LLM unavailable"""

        # Check basic prerequisites
        has_product_data = context.get("product_data_available", False)
        task_already_done = context.get("task_completed", False)
        is_blocked = context.get("is_blocked", False)

        # Decision logic
        if not has_product_data:
            return ReasoningResult(
                should_act=False,
                confidence=0.0,
                reasoning=f"Cannot act: no product data available for {task}",
                complexity="n/a",
                prerequisites_met=False,
                risks=["Missing required data"],
            )

        if task_already_done:
            return ReasoningResult(
                should_act=False,
                confidence=0.0,
                reasoning="Task already completed by another agent",
                complexity="n/a",
                prerequisites_met=True,
            )

        if is_blocked:
            return ReasoningResult(
                should_act=False,
                confidence=0.0,
                reasoning="Task is blocked by unmet dependencies",
                complexity="medium",
                prerequisites_met=False,
                risks=["Blocked dependencies"],
            )

        # Default: LLM failed, so we cannot reason safely
        return ReasoningResult(
            should_act=False,
            confidence=0.0,
            reasoning="LLM reasoning unavailable - defaulting to safe state (no action)",
            complexity="n/a",
            prerequisites_met=False,
            risks=["LLM unavailable"],
        )

    def calculate_dynamic_confidence(
        self, base_confidence: float, context_factors: Dict[str, Any]
    ) -> float:
        """
        Dynamically adjust confidence based on context factors.

        Factors that can affect confidence:
        - data_quality: 0.0-1.0
        - time_pressure: 0.0-1.0 (higher = more pressure)
        - prior_failures: int (number of previous failures)
        - complexity_score: 0.0-1.0
        """
        adjusted = base_confidence

        # Data quality adjustment
        data_quality = context_factors.get("data_quality", 1.0)
        adjusted *= data_quality

        # Prior failures reduce confidence
        prior_failures = context_factors.get("prior_failures", 0)
        if prior_failures > 0:
            adjusted *= 0.9**prior_failures  # Exponential decay

        # Complexity adjustment
        complexity = context_factors.get("complexity_score", 0.5)
        if complexity > 0.7:  # High complexity
            adjusted *= 0.9
        elif complexity < 0.3:  # Low complexity
            adjusted *= 1.1

        # Time pressure increases urgency but reduces confidence
        time_pressure = context_factors.get("time_pressure", 0.0)
        if time_pressure > 0.7:
            adjusted *= 0.95

        # Clamp to valid range
        return max(0.0, min(1.0, adjusted))


# Global singleton
_reasoning_engine = None


def get_reasoning_engine(provider=None) -> ReasoningEngine:
    """Get or create reasoning engine singleton"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine(provider)
    return _reasoning_engine
