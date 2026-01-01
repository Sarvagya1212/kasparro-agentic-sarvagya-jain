"""
Action Validator: Prevents hallucinated or out-of-scope agent actions.
Validates actions before they affect the real world.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AgentContext

logger = logging.getLogger("ActionValidator")


@dataclass
class PermittedAction:
    """Defines what actions an agent is permitted to take."""
    agent: str
    action: str
    requires_context: List[str] = field(default_factory=list)
    max_scope: str = "read"  # "read", "write", "execute"
    description: str = ""


@dataclass
class ValidationResult:
    """Result of action validation."""
    is_valid: bool
    reason: str
    violations: List[str] = field(default_factory=list)
    grounding_issues: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ActionValidator:
    """
    Validates agent actions before execution.
    Prevents hallucinated actions and scope violations.
    """

    # Define permitted actions per agent
    PERMITTED_ACTIONS: Dict[str, List[PermittedAction]] = {
        "DataAgent": [
            PermittedAction("DataAgent", "load_data", [], "read", "Load product data"),
            PermittedAction("DataAgent", "validate_schema", ["product_data"], "read"),
            PermittedAction("DataAgent", "fetch_product", [], "read"),
        ],
        "SyntheticDataAgent": [
            PermittedAction("SyntheticDataAgent", "generate_synthetic", ["product_data"], "write"),
            PermittedAction("SyntheticDataAgent", "create_competitor", ["product_data"], "write"),
        ],
        "AnalysisAgent": [
            PermittedAction("AnalysisAgent", "extract_benefits", ["product_data"], "read"),
            PermittedAction("AnalysisAgent", "generate_questions", ["product_data"], "read"),
            PermittedAction("AnalysisAgent", "analyze", ["product_data"], "read"),
        ],
        "DelegatorAgent": [
            PermittedAction("DelegatorAgent", "delegate", ["product_data"], "execute"),
            PermittedAction("DelegatorAgent", "delegate_analysis", ["product_data", "comparison_data"], "execute"),
            PermittedAction("DelegatorAgent", "coordinate_workers", [], "execute"),
        ],
        "ValidationAgent": [
            PermittedAction("ValidationAgent", "validate", ["analysis_results"], "read"),
            PermittedAction("ValidationAgent", "check_quality", [], "read"),
        ],
        "GenerationAgent": [
            PermittedAction("GenerationAgent", "generate", ["analysis_results"], "write"),
            PermittedAction("GenerationAgent", "create_faq", ["generated_questions"], "write"),
            PermittedAction("GenerationAgent", "create_product_page", ["product_data"], "write"),
            PermittedAction("GenerationAgent", "create_comparison", ["comparison_data"], "write"),
        ],
        "VerifierAgent": [
            PermittedAction("VerifierAgent", "verify", [], "read"),
            PermittedAction("VerifierAgent", "verify_outputs", [], "read"),
            PermittedAction("VerifierAgent", "audit", [], "read"),
        ],
    }

    # Actions that are always allowed (meta-actions)
    UNIVERSAL_ACTIONS: Set[str] = {"execute", "propose", "can_handle", "run"}

    def __init__(self):
        self.validation_log: List[Dict] = []

    def validate_action(
        self,
        agent: str,
        action: str,
        context: "AgentContext"
    ) -> ValidationResult:
        """
        Validate an agent's proposed action.

        Checks:
        1. Action is within agent's permitted scope
        2. Required context fields are present
        3. Action is not based on hallucinated data
        """
        violations = []
        grounding_issues = []

        # Universal actions are always allowed
        if action in self.UNIVERSAL_ACTIONS:
            return self._create_result(True, f"{action} is a universal action", agent, action)

        # Check if agent is known
        permitted = self.PERMITTED_ACTIONS.get(agent, [])
        if not permitted:
            # Unknown agent - allow but log warning
            logger.warning(f"Unknown agent '{agent}' - no permission rules defined")
            return self._create_result(True, "Unknown agent, no rules defined", agent, action)

        # Find matching permitted action
        matching_action = None
        for pa in permitted:
            if pa.action == action or action.startswith(pa.action):
                matching_action = pa
                break

        if not matching_action:
            violations.append(f"Action '{action}' not permitted for {agent}")
            allowed = [pa.action for pa in permitted]
            return self._create_result(
                False,
                f"Action not in permitted list: {allowed}",
                agent, action, violations
            )

        # Check required context fields
        for required_field in matching_action.requires_context:
            if not self._has_context_field(context, required_field):
                grounding_issues.append(f"Missing required context: {required_field}")

        if grounding_issues:
            return self._create_result(
                False,
                "Missing required context data",
                agent, action, [], grounding_issues
            )

        return self._create_result(True, "Action validated", agent, action)

    def check_data_grounding(
        self,
        output: Any,
        context: "AgentContext"
    ) -> List[str]:
        """
        Verify output references only data that exists in context.
        Returns list of ungrounded claims.
        """
        issues = []

        if isinstance(output, dict):
            # Check if output references non-existent products
            if "product_name" in output:
                if context.product_data:
                    if output["product_name"] != context.product_data.name:
                        issues.append(
                            f"Output references unknown product: {output['product_name']}"
                        )
                else:
                    issues.append("Output references product but no product in context")

            # Check if output contains fabricated ingredients
            if "ingredients" in output and context.product_data:
                known_ingredients = set(context.product_data.key_ingredients)
                for ing in output.get("ingredients", []):
                    if ing not in known_ingredients:
                        issues.append(f"Fabricated ingredient: {ing}")

        return issues

    def detect_fabrication(
        self,
        text: str,
        source_data: Dict[str, Any]
    ) -> List[str]:
        """
        Detect claims in text not grounded in source data.
        Simple pattern matching for common fabrication types.
        """
        issues = []

        # Check for specific claim patterns
        price_pattern = r"\$?\d+(?:\.\d{2})?"
        prices_in_text = re.findall(price_pattern, text)

        source_price = str(source_data.get("price", ""))
        for price in prices_in_text:
            if price and source_price and price not in source_price:
                issues.append(f"Unverified price claim: {price}")

        # Check for percentage claims
        percent_pattern = r"\d+%"
        percentages = re.findall(percent_pattern, text)
        for pct in percentages:
            if pct not in str(source_data):
                issues.append(f"Unverified percentage claim: {pct}")

        return issues

    def get_permitted_actions(self, agent: str) -> List[str]:
        """Get list of permitted action names for an agent."""
        permitted = self.PERMITTED_ACTIONS.get(agent, [])
        return [pa.action for pa in permitted]

    def _has_context_field(self, context: "AgentContext", field: str) -> bool:
        """Check if context has a field with data (not None or empty)."""
        value = getattr(context, field, None)
        # Check for None or empty collections
        if value is None:
            return False
        if isinstance(value, (list, dict, str)) and len(value) == 0:
            return False
        return True

    def _create_result(
        self,
        is_valid: bool,
        reason: str,
        agent: str,
        action: str,
        violations: List[str] = None,
        grounding_issues: List[str] = None
    ) -> ValidationResult:
        """Create and log validation result."""
        result = ValidationResult(
            is_valid=is_valid,
            reason=reason,
            violations=violations or [],
            grounding_issues=grounding_issues or []
        )

        # Log
        log_entry = {
            "timestamp": result.timestamp,
            "agent": agent,
            "action": action,
            "valid": is_valid,
            "reason": reason
        }
        self.validation_log.append(log_entry)

        status = "ALLOWED" if is_valid else "BLOCKED"
        logger.info(f"[{agent}] {action} → {status}: {reason}")

        return result

    def get_validation_log(self) -> List[Dict]:
        """Get full validation log."""
        return self.validation_log.copy()
