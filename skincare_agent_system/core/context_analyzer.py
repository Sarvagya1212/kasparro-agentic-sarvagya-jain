"""
Context Analyzer: Dynamic context assessment for agent proposals.
Replaces hardcoded priorities with context-driven scoring.
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.core.models import AgentContext

logger = logging.getLogger("ContextAnalyzer")


class ContextAnalyzer:
    """
    Analyzes context state to provide dynamic confidence and priority scores.

    Key principles:
    - Scores based on actual context state, not assumptions
    - Uses workflow phase detection for priority
    - Considers dependencies between agents
    - Learns from episodic memory when available
    """

    # Workflow phases and their priority weights
    PHASE_WEIGHTS = {
        "data_loading": 10,
        "data_augmentation": 9,
        "analysis": 8,
        "validation": 7,
        "generation": 6,
        "verification": 5,
    }

    def __init__(self):
        self._execution_history: List[str] = []
        self._success_rates: Dict[str, float] = {}

    def detect_workflow_phase(self, context: "AgentContext") -> str:
        """Detect current workflow phase based on context state."""
        if context.product_data is None:
            return "data_loading"

        if context.comparison_data is None:
            return "data_augmentation"

        if context.analysis_results is None:
            return "analysis"

        if not context.is_valid:
            return "validation"

        # Check if generation has occurred by looking at execution history
        generation_done = any(
            "GenerationAgent" in step for step in context.execution_history
        )

        if not generation_done:
            return "generation"

        return "verification"

    def get_base_priority(self, agent_type: str, context: "AgentContext") -> int:
        """
        Calculate base priority for agent type based on workflow phase.

        Returns:
            Priority score (higher = should execute sooner)
        """
        phase = self.detect_workflow_phase(context)
        phase_priority = self.PHASE_WEIGHTS.get(phase, 5)

        # Map agent types to phases they're most relevant for
        agent_phase_map = {
            "DataAgent": "data_loading",
            "SyntheticDataAgent": "data_augmentation",
            "DelegatorAgent": "analysis",
            "GenerationAgent": "generation",
            "VerifierAgent": "verification",
        }

        agent_phase = agent_phase_map.get(agent_type, "analysis")

        # Highest priority if agent matches current phase
        if agent_phase == phase:
            return phase_priority

        # Lower priority if we're past the agent's phase
        if self.PHASE_WEIGHTS.get(agent_phase, 0) > self.PHASE_WEIGHTS.get(phase, 0):
            return 0  # Already past this phase

        # Even lower priority if we're before the agent's phase
        return max(1, phase_priority - 3)

    def calculate_confidence_bonus(
        self, agent_name: str, context: "AgentContext"
    ) -> float:
        """
        Calculate confidence bonus based on context assessment.

        Returns:
            Bonus value to add to base confidence (can be negative)
        """
        bonus = 0.0

        # Bonus for agents in their optimal phase
        phase = self.detect_workflow_phase(context)
        agent_type = (
            agent_name.replace("Agent", "") + "Agent"
            if "Agent" not in agent_name
            else agent_name
        )

        agent_phase_map = {
            "DataAgent": "data_loading",
            "SyntheticDataAgent": "data_augmentation",
            "DelegatorAgent": "analysis",
            "GenerationAgent": "generation",
            "VerifierAgent": "verification",
        }

        if agent_phase_map.get(agent_type) == phase:
            bonus += 0.1  # Boost confidence when in optimal phase

        # Penalty for agents that have recently executed (prevent loops)
        recency_penalty = self._get_recency_penalty(agent_name)
        bonus -= recency_penalty

        # Bonus from historical success rate
        if agent_name in self._success_rates:
            success_rate = self._success_rates[agent_name]
            if success_rate > 0.8:
                bonus += 0.05
            elif success_rate < 0.5:
                bonus -= 0.1

        return bonus

    def _get_recency_penalty(self, agent_name: str) -> float:
        """
        Calculate penalty for recently executed agents to prevent loops.

        Returns:
            Penalty value (0.0 to 0.3)
        """
        if not self._execution_history:
            return 0.0

        # Check last 3 executions
        recent = self._execution_history[-3:]

        # Immediate repeat is heavily penalized
        if recent and recent[-1] == agent_name:
            return 0.3

        # Recent execution is moderately penalized
        if agent_name in recent:
            return 0.15

        return 0.0

    def record_execution(self, agent_name: str, success: bool = True):
        """Record agent execution for recency tracking."""
        self._execution_history.append(agent_name)

        # Update success rate
        if agent_name not in self._success_rates:
            self._success_rates[agent_name] = 1.0 if success else 0.0
        else:
            # Exponential moving average
            alpha = 0.3
            current = 1.0 if success else 0.0
            self._success_rates[agent_name] = (
                alpha * current + (1 - alpha) * self._success_rates[agent_name]
            )

    def assess_data_readiness(self, context: "AgentContext") -> float:
        """
        Score how ready the context is for data loading.

        Returns:
            Score 0.0-1.0 (higher = more ready for data loading)
        """
        if context.product_data is None:
            return 1.0  # Definitely needs data

        # Check data staleness (if we have timestamps)
        if hasattr(context, "data_loaded_at"):
            import datetime

            age = (datetime.datetime.now() - context.data_loaded_at).seconds
            if age > 3600:  # Over 1 hour
                return 0.6

        return 0.0  # Data already loaded

    def assess_analysis_readiness(self, context: "AgentContext") -> float:
        """
        Score how ready the context is for analysis.

        Returns:
            Score 0.0-1.0 (higher = more ready for analysis)
        """
        if context.product_data is None:
            return 0.0  # Can't analyze without data

        if context.comparison_data is None:
            return 0.3  # Can do partial analysis

        if context.analysis_results is not None:
            return 0.0  # Already analyzed

        return 1.0  # Ready for analysis

    def assess_generation_readiness(self, context: "AgentContext") -> float:
        """
        Score how ready the context is for content generation.

        Returns:
            Score 0.0-1.0 (higher = more ready for generation)
        """
        if not context.is_valid:
            return 0.0  # Must be validated first

        # Check if already generated
        generation_done = any(
            "GenerationAgent" in step for step in context.execution_history
        )

        if generation_done:
            return 0.0

        return 1.0

    def get_context_bonus(self, agent_name: str, context: "AgentContext") -> float:
        """
        Get overall context-based confidence bonus for an agent.

        This is the main entry point for external callers.

        Returns:
            Bonus value to add to base confidence
        """
        return self.calculate_confidence_bonus(agent_name, context)


# Singleton instance
_analyzer_instance: Optional[ContextAnalyzer] = None


def get_context_analyzer() -> ContextAnalyzer:
    """Get or create the singleton ContextAnalyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ContextAnalyzer()
    return _analyzer_instance
