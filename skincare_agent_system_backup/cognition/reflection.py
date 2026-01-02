"""
Self-Reflection: Agents critique their own outputs.
Implements the "never trust, always verify" pattern.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.core.models import AgentContext


logger = logging.getLogger("Reflection")


@dataclass
class ReflectionIssue:
    """An issue found during self-reflection."""

    severity: str  # "critical", "warning", "info"
    category: str  # "accuracy", "completeness", "safety", "logic"
    description: str
    suggestion: Optional[str] = None


@dataclass
class ReflectionResult:
    """Result of self-reflection on an output."""

    is_acceptable: bool
    issues: List[ReflectionIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_issue(
        self, severity: str, category: str, description: str, suggestion: str = None
    ):
        """Add an issue to the reflection."""
        issue = ReflectionIssue(
            severity=severity,
            category=category,
            description=description,
            suggestion=suggestion,
        )
        self.issues.append(issue)
        if suggestion:
            self.suggestions.append(suggestion)

    def has_critical_issues(self) -> bool:
        """Check if there are critical issues."""
        return any(i.severity == "critical" for i in self.issues)


class SelfReflector:
    """
    Agent self-critique capability.
    Allows agents to check their own work before finalizing.
    """

    def __init__(self):
        self.reflection_log: List[Dict] = []

    def reflect_on_output(
        self, agent_name: str, output: Any, context: "AgentContext" = None
    ) -> ReflectionResult:
        """
        Perform self-reflection on an agent's output.

        Args:
            agent_name: Name of the agent
            output: The output to reflect on
            context: Optional context for additional checks

        Returns:
            ReflectionResult with issues and suggestions
        """
        result = ReflectionResult(is_acceptable=True, confidence=1.0)

        # Reflect based on agent type
        if agent_name == "DataAgent":
            result = self._reflect_data_agent(output, context, result)
        elif agent_name == "AnalysisAgent" or agent_name == "DelegatorAgent":
            result = self._reflect_analysis_agent(output, context, result)
        elif agent_name == "GenerationAgent":
            result = self._reflect_generation_agent(output, context, result)
        elif agent_name == "ValidationAgent":
            result = self._reflect_validation_agent(output, context, result)
        else:
            result = self._generic_reflection(output, result)

        # Determine acceptability
        result.is_acceptable = not result.has_critical_issues()

        # Log reflection
        self._log_reflection(agent_name, result)

        return result

    def _reflect_data_agent(
        self, output: Any, context: "AgentContext", result: ReflectionResult
    ) -> ReflectionResult:
        """Reflect on DataAgent output."""
        result.reasoning = "Checking if product data was loaded correctly"

        if context and context.product_data:
            # Check completeness
            product = context.product_data
            if not product.name:
                result.add_issue(
                    "critical",
                    "completeness",
                    "Product name is missing",
                    "Ensure data source contains product name",
                )
            if not product.key_ingredients:
                result.add_issue(
                    "warning",
                    "completeness",
                    "No key ingredients specified",
                    "Add ingredient list for better content",
                )
            if product.price is None or product.price <= 0:
                result.add_issue(
                    "warning",
                    "accuracy",
                    "Invalid or missing price",
                    "Verify price data",
                )

            # Calculate confidence
            fields_present = sum(
                [
                    bool(product.name),
                    bool(product.brand),
                    bool(product.key_ingredients),
                    bool(product.price),
                    bool(product.benefits),
                ]
            )
            result.confidence = fields_present / 5.0
        else:
            result.add_issue(
                "critical",
                "completeness",
                "No product data in context after DataAgent run",
                "Check data loading logic",
            )

        return result

    def _reflect_analysis_agent(
        self, output: Any, context: "AgentContext", result: ReflectionResult
    ) -> ReflectionResult:
        """Reflect on AnalysisAgent/DelegatorAgent output."""
        result.reasoning = "Checking if analysis produced sufficient content"

        if context and context.analysis_results:
            analysis = context.analysis_results

            # Check benefits
            if not analysis.benefits or len(analysis.benefits) < 2:
                result.add_issue(
                    "warning",
                    "completeness",
                    "Very few benefits extracted",
                    "Review benefits extraction logic",
                )

            # Check questions
            if context.generated_questions:
                q_count = len(context.generated_questions)
                if q_count < 15:
                    result.add_issue(
                        "warning",
                        "completeness",
                        f"Only {q_count} questions generated (target: 15)",
                        "Increase question generation",
                    )
                result.confidence = min(1.0, q_count / 15.0)
            else:
                result.add_issue(
                    "critical",
                    "completeness",
                    "No questions generated",
                    "Check question generator",
                )
        else:
            result.add_issue(
                "critical",
                "completeness",
                "No analysis results in context",
                "Verify analysis pipeline",
            )

        return result

    def _reflect_generation_agent(
        self, output: Any, context: "AgentContext", result: ReflectionResult
    ) -> ReflectionResult:
        """Reflect on GenerationAgent output."""
        result.reasoning = "Checking if output files were generated correctly"

        from pathlib import Path

        output_dir = Path("output")

        expected_files = ["faq.json", "product_page.json", "comparison_page.json"]
        missing = []

        for fname in expected_files:
            if not (output_dir / fname).exists():
                missing.append(fname)

        if missing:
            result.add_issue(
                "critical",
                "completeness",
                f"Missing output files: {', '.join(missing)}",
                "Check generation logic for these templates",
            )
        else:
            result.confidence = 1.0

        return result

    def _reflect_validation_agent(
        self, output: Any, context: "AgentContext", result: ReflectionResult
    ) -> ReflectionResult:
        """Reflect on ValidationAgent output."""
        result.reasoning = "Checking if validation was thorough"

        if context:
            if context.validation_errors:
                result.add_issue(
                    "info",
                    "logic",
                    f"Validation found {len(context.validation_errors)} issues",
                    None,
                )

            if context.is_valid:
                result.confidence = 1.0
            else:
                result.confidence = 0.5

        return result

    def _generic_reflection(
        self, output: Any, result: ReflectionResult
    ) -> ReflectionResult:
        """Generic reflection for unknown agents."""
        result.reasoning = "Performing basic output validation"

        if output is None:
            result.add_issue(
                "warning",
                "completeness",
                "Output is None",
                "Ensure agent produces output",
            )
            result.confidence = 0.5

        return result

    def _log_reflection(self, agent_name: str, result: ReflectionResult):
        """Log reflection for audit trail."""
        log_entry = {
            "timestamp": result.timestamp,
            "agent": agent_name,
            "acceptable": result.is_acceptable,
            "confidence": result.confidence,
            "issue_count": len(result.issues),
            "reasoning": result.reasoning,
        }
        self.reflection_log.append(log_entry)
        logger.info(
            f"[{agent_name}] Reflection: {'PASS' if result.is_acceptable else 'FAIL'} "
            f"(confidence: {result.confidence:.2f}, issues: {len(result.issues)})"
        )

    def get_reflection_log(self) -> List[Dict]:
        """Get full reflection log."""
        return self.reflection_log.copy()

    def suggest_improvements(
        self, output: Any, context: "AgentContext" = None
    ) -> List[str]:
        """Generate improvement suggestions for an output."""
        suggestions = []

        if context:
            if not context.product_data:
                suggestions.append("Load product data before proceeding")
            if context.product_data and not context.comparison_data:
                suggestions.append("Generate comparison product for complete output")
            if context.analysis_results and not context.is_valid:
                suggestions.append("Address validation issues before generation")

        return suggestions
