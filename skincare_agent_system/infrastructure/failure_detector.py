"""
Failure Detector: Handles system design and inter-agent misalignment failures.
Implements role compliance checking and inter-agent communication auditing.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.models import AgentContext
    from skincare_agent_system.core.proposals import Event
    from skincare_agent_system.core.state_manager import StateManager

logger = logging.getLogger("FailureDetector")


@dataclass
class RoleViolation:
    """A detected role boundary violation."""

    agent: str
    attempted_action: str
    permitted_actions: List[str]
    severity: str  # "warning", "critical"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class HandoffAuditResult:
    """Result of inter-agent handoff audit."""

    from_agent: str
    to_agent: str
    is_valid: bool
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    critical_info_missing: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# Define what context fields each agent MUST receive
REQUIRED_HANDOFF_FIELDS: Dict[str, Dict[str, List[str]]] = {
    "DataAgent": {
        "SyntheticDataAgent": ["product_data"],
        "DelegatorAgent": ["product_data"],
    },
    "SyntheticDataAgent": {
        "DelegatorAgent": ["product_data", "comparison_data"],
    },
    "DelegatorAgent": {
        "GenerationAgent": ["product_data", "analysis_results", "is_valid"],
    },
    "GenerationAgent": {
        "VerifierAgent": ["product_data", "analysis_results"],
    },
}


class RoleComplianceChecker:
    """
    Detects agents disobeying their role specifications.
    Ensures agents stay within their defined boundaries.
    """

    # Define role boundaries
    ROLE_BOUNDARIES: Dict[str, Dict[str, Any]] = {
        "DataAgent": {
            "permitted_scopes": ["read"],
            "can_modify_context": ["product_data"],
            "forbidden_actions": ["delete", "write_file", "execute_command"],
        },
        "SyntheticDataAgent": {
            "permitted_scopes": ["read", "write"],
            "can_modify_context": ["comparison_data"],
            "forbidden_actions": ["delete", "execute_command"],
        },
        "AnalysisAgent": {
            "permitted_scopes": ["read"],
            "can_modify_context": ["analysis_results", "generated_questions"],
            "forbidden_actions": ["delete", "write_file"],
        },
        "DelegatorAgent": {
            "permitted_scopes": ["read", "execute"],
            "can_modify_context": ["analysis_results", "is_valid"],
            "forbidden_actions": ["delete"],
        },
        "GenerationAgent": {
            "permitted_scopes": ["read", "write"],
            "can_modify_context": [],
            "forbidden_actions": ["delete", "execute_command"],
        },
        "VerifierAgent": {
            "permitted_scopes": ["read"],
            "can_modify_context": [],
            "forbidden_actions": ["modify", "delete", "write"],
        },
    }

    def __init__(self):
        self.violations: List[RoleViolation] = []

    def check_role_boundaries(self, agent: "BaseAgent", action: str) -> bool:
        """
        Verify agent stays within its defined role.

        Returns:
            True if action is within role boundaries
        """
        agent_name = agent.name
        boundaries = self.ROLE_BOUNDARIES.get(agent_name, {})

        if not boundaries:
            # Unknown agent - allow but log
            logger.warning(f"No role boundaries defined for {agent_name}")
            return True

        # Check forbidden actions
        forbidden = boundaries.get("forbidden_actions", [])
        for forbidden_action in forbidden:
            if forbidden_action in action.lower():
                self._record_violation(
                    agent_name, action, forbidden, severity="critical"
                )
                return False

        return True

    def detect_scope_creep(self, agent: str, actions: List[str]) -> List[str]:
        """
        Detect when agent attempts actions outside its scope.

        Args:
            agent: Agent name
            actions: List of actions agent has attempted

        Returns:
            List of out-of-scope actions
        """
        boundaries = self.ROLE_BOUNDARIES.get(agent, {})
        permitted_scopes = set(boundaries.get("permitted_scopes", []))

        out_of_scope = []
        for action in actions:
            action_scope = self._infer_action_scope(action)
            if action_scope not in permitted_scopes:
                out_of_scope.append(action)

        return out_of_scope

    def check_context_modification(self, agent: str, modified_field: str) -> bool:
        """Check if agent is allowed to modify a context field."""
        boundaries = self.ROLE_BOUNDARIES.get(agent, {})
        allowed_fields = boundaries.get("can_modify_context", [])

        if modified_field not in allowed_fields:
            logger.warning(
                f"{agent} attempted to modify '{modified_field}' "
                f"but only allowed: {allowed_fields}"
            )
            return False
        return True

    def _infer_action_scope(self, action: str) -> str:
        """Infer scope from action name."""
        action_lower = action.lower()
        if any(kw in action_lower for kw in ["write", "create", "generate", "save"]):
            return "write"
        elif any(kw in action_lower for kw in ["execute", "run", "delegate"]):
            return "execute"
        elif any(kw in action_lower for kw in ["delete", "remove"]):
            return "delete"
        return "read"

    def _record_violation(
        self, agent: str, action: str, permitted: List[str], severity: str = "warning"
    ):
        """Record a role violation."""
        violation = RoleViolation(
            agent=agent,
            attempted_action=action,
            permitted_actions=permitted,
            severity=severity,
        )
        self.violations.append(violation)
        logger.error(
            f"ROLE VIOLATION: {agent} attempted '{action}' " f"(severity: {severity})"
        )

    def get_violations(self) -> List[RoleViolation]:
        """Get all recorded violations."""
        return self.violations.copy()


class InterAgentAuditor:
    """
    Monitors inter-agent communication for misalignment.
    Ensures critical information is passed correctly between agents.
    """

    def __init__(self):
        self.audit_log: List[HandoffAuditResult] = []

    def audit_handoff(
        self, from_agent: str, to_agent: str, context: "AgentContext"
    ) -> HandoffAuditResult:
        """
        Verify critical information is passed correctly during handoff.

        Args:
            from_agent: Agent handing off
            to_agent: Agent receiving
            context: Current context state

        Returns:
            Audit result with any missing fields
        """
        result = HandoffAuditResult(
            from_agent=from_agent, to_agent=to_agent, is_valid=True
        )

        # Get required fields for this handoff
        required = REQUIRED_HANDOFF_FIELDS.get(from_agent, {}).get(to_agent, [])

        for field_name in required:
            value = getattr(context, field_name, None)
            if value is None:
                result.missing_fields.append(field_name)
                result.is_valid = False

                # Check if this is critical
                if field_name in ["product_data", "is_valid"]:
                    result.critical_info_missing = True

        # Log result
        self._log_audit(result)
        return result

    def detect_information_loss(
        self, before: "AgentContext", after: "AgentContext"
    ) -> List[str]:
        """
        Identify critical data lost during processing.

        Args:
            before: Context before agent execution
            after: Context after agent execution

        Returns:
            List of lost fields
        """
        critical_fields = ["product_data", "comparison_data", "analysis_results"]
        lost = []

        for field in critical_fields:
            before_val = getattr(before, field, None)
            after_val = getattr(after, field, None)

            if before_val is not None and after_val is None:
                lost.append(field)
                logger.error(f"INFORMATION LOSS: {field} was lost during processing")

        return lost

    def verify_message_integrity(self, event: "Event") -> bool:
        """
        Ensure events contain required information.

        Args:
            event: Event to verify

        Returns:
            True if event has all required fields
        """
        required_fields = ["type", "source"]

        for field in required_fields:
            if not getattr(event, field, None):
                logger.warning(f"Event missing required field: {field}")
                return False

        return True

    def _log_audit(self, result: HandoffAuditResult):
        """Log audit result."""
        self.audit_log.append(result)

        status = "OK" if result.is_valid else "FAILED"
        logger.info(f"Handoff audit {result.from_agent}→{result.to_agent}: {status}")
        if result.missing_fields:
            logger.warning(f"Missing fields: {result.missing_fields}")

    def get_audit_log(self) -> List[HandoffAuditResult]:
        """Get full audit log."""
        return self.audit_log.copy()


class FailureRecovery:
    """
    Handles detected failures gracefully.
    Provides recovery actions for different failure types.
    """

    def __init__(self):
        self.recovery_log: List[Dict] = []

    def on_role_violation(
        self, agent: str, violation: str, state_manager: "StateManager" = None
    ) -> str:
        """
        Handle role boundary violation.

        Returns:
            Recovery action taken
        """
        action = "block_and_log"

        self._log_recovery(agent, "role_violation", violation, action)
        logger.error(f"Role violation by {agent}: {violation}")

        return action

    def on_communication_failure(
        self,
        from_agent: str,
        to_agent: str,
        missing_info: List[str],
        state_manager: "StateManager" = None,
    ) -> str:
        """
        Handle inter-agent communication failure.

        Returns:
            Recovery action taken
        """
        action = "retry_with_context_rebuild"

        self._log_recovery(
            f"{from_agent}→{to_agent}",
            "communication_failure",
            f"Missing: {missing_info}",
            action,
        )

        return action

    def rollback_to_safe_state(self, state_manager: "StateManager") -> bool:
        """
        Rollback to last known good state.

        Returns:
            True if rollback successful
        """
        if state_manager:
            success = state_manager.rollback()
            self._log_recovery(
                "system",
                "rollback",
                "Rollback requested",
                "success" if success else "failed",
            )
            return success
        return False

    def _log_recovery(
        self, source: str, failure_type: str, description: str, action: str
    ):
        """Log recovery action."""
        self.recovery_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "source": source,
                "failure_type": failure_type,
                "description": description,
                "action": action,
            }
        )

    def get_recovery_log(self) -> List[Dict]:
        """Get full recovery log."""
        return self.recovery_log.copy()
