"""
Evaluation: Granular failure analysis with taxonomy.
Categorizes failures for systematic improvement.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from skincare_agent_system.infrastructure.llm_client import get_llm_client

from .evaluation_dataset import TestCase

logger = logging.getLogger("Evaluation")


class FailureCategory(Enum):
    """Taxonomy of failure categories."""

    SYSTEM_DESIGN = "system_design"  # Architecture/routing issues
    INTER_AGENT_MISALIGNMENT = "inter_agent"  # Communication failures
    TOOL_FAILURE = "tool_failure"  # Tool execution errors
    VALIDATION_ERROR = "validation_error"  # Data validation issues
    SAFETY_VIOLATION = "safety_violation"  # Guardrails triggered
    TIMEOUT = "timeout"  # Execution timeout
    UNKNOWN = "unknown"  # Unclassified


@dataclass
class FailureRecord:
    """Record of a single failure."""

    category: FailureCategory
    agent: str
    error_message: str
    context: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    severity: str = "medium"  # low, medium, high, critical


class FailureAnalyzer:
    """
    Analyzes and categorizes failures for systematic improvement.
    """

    def __init__(self):
        self.failures: List[FailureRecord] = []

    def categorize_failure(
        self, error: str, agent: str, context: Dict[str, Any] = None
    ) -> FailureCategory:
        """
        Categorize a failure based on error message and context.

        Args:
            error: Error message
            agent: Agent that failed
            context: Additional context

        Returns:
            Failure category
        """
        error_lower = error.lower()

        # Safety violations
        if any(kw in error_lower for kw in ["blocked", "forbidden", "safety"]):
            category = FailureCategory.SAFETY_VIOLATION
            severity = "high"
        # Validation errors
        elif any(kw in error_lower for kw in ["validation", "invalid", "missing"]):
            category = FailureCategory.VALIDATION_ERROR
            severity = "medium"
        # Tool failures
        elif any(kw in error_lower for kw in ["tool", "not found", "execution"]):
            category = FailureCategory.TOOL_FAILURE
            severity = "medium"
        # Inter-agent issues
        elif any(kw in error_lower for kw in ["context", "handoff", "communication"]):
            category = FailureCategory.INTER_AGENT_MISALIGNMENT
            severity = "high"
        # System design
        elif any(kw in error_lower for kw in ["routing", "state", "loop"]):
            category = FailureCategory.SYSTEM_DESIGN
            severity = "critical"
        # Timeout
        elif "timeout" in error_lower:
            category = FailureCategory.TIMEOUT
            severity = "medium"
        else:
            category = FailureCategory.UNKNOWN
            severity = "low"

        # Record failure
        record = FailureRecord(
            category=category,
            agent=agent,
            error_message=error,
            context=context or {},
            severity=severity,
        )
        self.failures.append(record)

        logger.info(f"Failure categorized: {category.value} ({severity})")
        return category

    def get_failure_report(self) -> Dict[str, Any]:
        """Generate failure analysis report."""
        if not self.failures:
            return {"total": 0, "message": "No failures recorded"}

        # Count by category
        by_category = {}
        by_agent = {}
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for f in self.failures:
            cat = f.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_agent[f.agent] = by_agent.get(f.agent, 0) + 1
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

        return {
            "total": len(self.failures),
            "by_category": by_category,
            "by_agent": by_agent,
            "by_severity": by_severity,
            "recent_failures": [
                {
                    "category": f.category.value,
                    "agent": f.agent,
                    "message": f.error_message[:100],
                    "timestamp": f.timestamp,
                }
                for f in self.failures[-5:]
            ],
        }

    def get_improvement_suggestions(self) -> List[str]:
        """Generate improvement suggestions based on failures."""
        suggestions = []
        report = self.get_failure_report()

        if report["total"] == 0:
            return ["No failures to analyze."]

        by_cat = report.get("by_category", {})

        if by_cat.get("system_design", 0) > 0:
            suggestions.append(
                "Review orchestrator routing logic and state transitions."
            )
        if by_cat.get("inter_agent", 0) > 0:
            suggestions.append(
                "Check AgentContext handoffs and data consistency between agents."
            )
        if by_cat.get("tool_failure", 0) > 0:
            suggestions.append(
                "Verify ToolRegistry configuration and tool implementations."
            )
        if by_cat.get("validation_error", 0) > 0:
            suggestions.append("Review Pydantic models and validation thresholds.")
        if by_cat.get("safety_violation", 0) > 0:
            suggestions.append(
                "Audit guardrails configuration for overly strict rules."
            )

        return suggestions if suggestions else ["No specific suggestions."]


class LLMJudge:
    """
    LLM-as-a-Judge for evaluating agent traces.
    """

    def __init__(self):
        self.client = get_llm_client()

    def evaluate_trace(
        self, trace_summary: Dict[str, Any], test_case: TestCase
    ) -> Dict[str, Any]:
        """
        Evaluate a trace against a test case.
        """
        if not self.client.is_available():
            logger.warning("LLMJudge: LLM not available - skipping evaluation")
            return {"score": 0.0, "reason": "LLM not available"}

        # Construct evaluation prompt
        prompt = f"""
You are an expert AI system evaluator. Grade the following agent execution.

### Test Case: {test_case.id}
**Input Data**: {json.dumps(test_case.input_data, indent=2)}
**Expected Output**: {json.dumps(test_case.expected_output, indent=2)}
**Evaluation Criteria**:
{chr(10).join(f"- {c}" for c in test_case.criteria)}

### Actual Execution Trace
**Status**: {trace_summary.get('status')}
**Events**: {trace_summary.get('total_events')}
**Errors**: {trace_summary.get('errors')}
**Output**: (See events for details if available in summary)

Evaluate the execution based on the criteria.
Return JSON with:
- "score" (0.0 to 1.0)
- "reason" (explanation)
- "failures" (list of specific criteria failures)
"""
        try:
            result = self.client.generate_json(
                prompt, temperature=0.1, agent_identity="agent_judge"
            )
            return result
        except Exception as e:
            logger.error(f"LLM Judge failed: {e}")
            return {"score": 0.0, "reason": f"Evaluation error: {str(e)}"}
