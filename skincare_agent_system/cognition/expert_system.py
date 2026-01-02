"""
Expert System: Rule-based reasoning for LLM-free autonomous decisions.
Implements Phase 7 of autonomy upgrades.

Provides:
- Rule-based expert system with weighted rules
- Decision trees with learned weights from history
- Confidence calibration from episodic memory
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.cognition.memory import EpisodicMemory
    from skincare_agent_system.core.models import AgentContext

logger = logging.getLogger("ExpertSystem")


@dataclass
class Rule:
    """A rule in the expert system."""

    id: str
    name: str
    condition: Callable[["AgentContext"], bool]
    action: str
    agent: str
    base_weight: float = 1.0
    learned_weight: float = 1.0

    @property
    def effective_weight(self) -> float:
        return self.base_weight * self.learned_weight


@dataclass
class Decision:
    """A decision made by the expert system."""

    agent: str
    action: str
    confidence: float
    rules_fired: List[str]
    reasoning: List[str]


class ExpertSystem:
    """
    PHASE 7: Rule-based expert system for LLM-free reasoning.
    Uses weighted rules and historical calibration for decisions.
    """

    def __init__(self):
        self.rules: List[Rule] = []
        self._memory: Optional[Any] = None
        self._decision_history: List[Decision] = []
        self._initialize_default_rules()

    def set_memory(self, memory: Any):
        """Connect to episodic memory for calibration."""
        self._memory = memory
        logger.info("ExpertSystem connected to memory for calibration")

    def _initialize_default_rules(self):
        """Initialize default reasoning rules."""
        # Data loading rules
        self.add_rule(
            Rule(
                id="R001",
                name="NoProductData",
                condition=lambda ctx: ctx.product_data is None,
                action="load_product_data",
                agent="DataAgent",
                base_weight=1.0,
            )
        )

        self.add_rule(
            Rule(
                id="R002",
                name="NoComparisonData",
                condition=lambda ctx: ctx.product_data is not None
                and ctx.comparison_data is None,
                action="generate_comparison_data",
                agent="SyntheticDataAgent",
                base_weight=0.95,
            )
        )

        # Analysis rules
        self.add_rule(
            Rule(
                id="R003",
                name="DataReadyNoAnalysis",
                condition=lambda ctx: (
                    ctx.product_data is not None
                    and ctx.comparison_data is not None
                    and ctx.analysis_results is None
                ),
                action="run_analysis",
                agent="DelegatorAgent",
                base_weight=0.9,
            )
        )

        self.add_rule(
            Rule(
                id="R004",
                name="AnalysisNotValidated",
                condition=lambda ctx: (
                    ctx.analysis_results is not None and not ctx.is_valid
                ),
                action="validate_analysis",
                agent="DelegatorAgent",
                base_weight=0.85,
            )
        )

        # Generation rules
        self.add_rule(
            Rule(
                id="R005",
                name="ReadyForGeneration",
                condition=lambda ctx: ctx.is_valid and self._needs_generation(ctx),
                action="generate_content",
                agent="GenerationAgent",
                base_weight=0.88,
            )
        )

        # Verification rules
        self.add_rule(
            Rule(
                id="R006",
                name="ReadyForVerification",
                condition=lambda ctx: ctx.is_valid and self._has_outputs(ctx),
                action="verify_outputs",
                agent="VerifierAgent",
                base_weight=0.92,
            )
        )

        logger.info(f"ExpertSystem initialized with {len(self.rules)} rules")

    def _needs_generation(self, context: "AgentContext") -> bool:
        """Check if generation is needed."""
        from pathlib import Path

        output_dir = Path("output")
        return not (output_dir / "faq.json").exists()

    def _has_outputs(self, context: "AgentContext") -> bool:
        """Check if outputs exist."""
        from pathlib import Path

        output_dir = Path("output")
        return (output_dir / "faq.json").exists() and (
            output_dir / "product_page.json"
        ).exists()

    def add_rule(self, rule: Rule):
        """Add a rule to the system."""
        self.rules.append(rule)

    def evaluate(self, context: "AgentContext") -> List[Decision]:
        """
        Evaluate all rules against context and return decisions.
        """
        decisions = []
        fired_rules = []

        for rule in self.rules:
            try:
                if rule.condition(context):
                    fired_rules.append(rule)
                    logger.debug(f"Rule fired: {rule.name} -> {rule.agent}")
            except Exception as e:
                logger.warning(f"Rule {rule.id} evaluation failed: {e}")

        if not fired_rules:
            return []

        # Group by agent
        agent_rules: Dict[str, List[Rule]] = {}
        for rule in fired_rules:
            if rule.agent not in agent_rules:
                agent_rules[rule.agent] = []
            agent_rules[rule.agent].append(rule)

        # Create decisions with aggregated confidence
        for agent, rules in agent_rules.items():
            # Calculate confidence from weighted rules
            total_weight = sum(r.effective_weight for r in rules)
            max_possible = len(rules) * 1.2  # Maximum if all weights were boosted
            confidence = min(1.0, total_weight / max(1, max_possible))

            # Apply historical calibration
            confidence = self._calibrate_confidence(agent, confidence)

            decision = Decision(
                agent=agent,
                action=rules[0].action,  # Primary action
                confidence=confidence,
                rules_fired=[r.id for r in rules],
                reasoning=[f"Rule {r.name}: {r.action}" for r in rules],
            )
            decisions.append(decision)

        # Sort by confidence
        decisions.sort(key=lambda d: d.confidence, reverse=True)

        logger.info(f"Expert system produced {len(decisions)} decisions")
        return decisions

    def _calibrate_confidence(self, agent: str, base_confidence: float) -> float:
        """
        PHASE 7: Calibrate confidence using historical success rates.
        """
        if self._memory is None:
            return base_confidence

        try:
            success_rate = self._memory.episodic.get_success_rate(agent)
            if success_rate > 0:
                # Blend base confidence with historical performance
                calibrated = base_confidence * (0.6 + 0.4 * success_rate)
                logger.debug(
                    f"Calibrated {agent}: {base_confidence:.2f} -> {calibrated:.2f} (SR: {success_rate:.2f})"
                )
                return calibrated
        except Exception:
            pass

        return base_confidence

    def update_weights_from_outcome(self, agent: str, action: str, success: bool):
        """
        Learn from outcomes by adjusting rule weights.
        """
        for rule in self.rules:
            if rule.agent == agent and rule.action == action:
                if success:
                    rule.learned_weight = min(1.5, rule.learned_weight * 1.05)
                else:
                    rule.learned_weight = max(0.5, rule.learned_weight * 0.95)
                logger.info(
                    f"Rule {rule.id} weight adjusted to {rule.learned_weight:.2f}"
                )

    def get_best_decision(self, context: "AgentContext") -> Optional[Decision]:
        """Get the highest-confidence decision."""
        decisions = self.evaluate(context)
        return decisions[0] if decisions else None


class DecisionTree:
    """
    PHASE 7: Simple decision tree for structured reasoning.
    """

    def __init__(self):
        self.nodes: Dict[str, Dict] = {}
        self._build_default_tree()

    def _build_default_tree(self):
        """Build default decision tree for content generation workflow."""
        self.nodes = {
            "root": {
                "question": "has_product_data",
                "yes": "check_comparison",
                "no": "DataAgent",
            },
            "check_comparison": {
                "question": "has_comparison_data",
                "yes": "check_analysis",
                "no": "SyntheticDataAgent",
            },
            "check_analysis": {
                "question": "has_analysis",
                "yes": "check_validation",
                "no": "DelegatorAgent",
            },
            "check_validation": {
                "question": "is_valid",
                "yes": "check_generation",
                "no": "DelegatorAgent",
            },
            "check_generation": {
                "question": "has_outputs",
                "yes": "VerifierAgent",
                "no": "GenerationAgent",
            },
        }

    def decide(self, context: "AgentContext") -> str:
        """Traverse tree to make decision."""
        current = "root"
        visited = []

        while current in self.nodes:
            node = self.nodes[current]
            question = node["question"]
            visited.append(f"{current}:{question}")

            answer = self._evaluate_question(question, context)
            next_node = node["yes"] if answer else node["no"]

            if next_node not in self.nodes:
                logger.info(
                    f"Decision tree path: {' -> '.join(visited)} -> {next_node}"
                )
                return next_node

            current = next_node

        return "DelegatorAgent"  # Default fallback

    def _evaluate_question(self, question: str, context: "AgentContext") -> bool:
        """Evaluate a decision tree question."""
        from pathlib import Path

        evaluators = {
            "has_product_data": lambda c: c.product_data is not None,
            "has_comparison_data": lambda c: c.comparison_data is not None,
            "has_analysis": lambda c: c.analysis_results is not None,
            "is_valid": lambda c: c.is_valid,
            "has_outputs": lambda c: (Path("output") / "faq.json").exists(),
        }

        evaluator = evaluators.get(question)
        if evaluator:
            return evaluator(context)

        return False


class ConfidenceCalibrator:
    """
    PHASE 7: Calibrates agent confidence based on historical data.
    """

    def __init__(self, memory: Optional[Any] = None):
        self._memory = memory
        self._calibration_cache: Dict[str, float] = {}

    def set_memory(self, memory: Any):
        self._memory = memory

    def calibrate(self, agent: str, base_confidence: float) -> float:
        """
        Apply Platt scaling-like calibration based on history.
        """
        if self._memory is None:
            return base_confidence

        # Check cache
        if agent in self._calibration_cache:
            factor = self._calibration_cache[agent]
            return min(1.0, base_confidence * factor)

        try:
            success_rate = self._memory.episodic.get_success_rate(agent)
            if success_rate > 0:
                # Calculate calibration factor
                # High success rate -> boost, low -> reduce
                factor = 0.5 + 0.5 * success_rate
                self._calibration_cache[agent] = factor
                return min(1.0, base_confidence * factor)
        except Exception:
            pass

        return base_confidence

    def recalibrate(self, agent: str, predicted: float, actual_success: bool):
        """
        Update calibration based on outcome.
        """
        current_factor = self._calibration_cache.get(agent, 1.0)

        if actual_success and predicted < 0.7:
            # Under-confident: boost
            new_factor = min(1.2, current_factor * 1.05)
        elif not actual_success and predicted > 0.7:
            # Over-confident: reduce
            new_factor = max(0.8, current_factor * 0.95)
        else:
            new_factor = current_factor

        self._calibration_cache[agent] = new_factor
        logger.debug(f"Recalibrated {agent}: {current_factor:.2f} -> {new_factor:.2f}")


# Singleton instances
_expert_system: Optional[ExpertSystem] = None
_decision_tree: Optional[DecisionTree] = None
_calibrator: Optional[ConfidenceCalibrator] = None


def get_expert_system() -> ExpertSystem:
    """Get or create the expert system singleton."""
    global _expert_system
    if _expert_system is None:
        _expert_system = ExpertSystem()
    return _expert_system


def get_decision_tree() -> DecisionTree:
    """Get or create the decision tree singleton."""
    global _decision_tree
    if _decision_tree is None:
        _decision_tree = DecisionTree()
    return _decision_tree


def get_calibrator() -> ConfidenceCalibrator:
    """Get or create the calibrator singleton."""
    global _calibrator
    if _calibrator is None:
        _calibrator = ConfidenceCalibrator()
    return _calibrator
