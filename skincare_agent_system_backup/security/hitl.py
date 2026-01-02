"""
Human-in-the-Loop (HITL) Gate: Requires human authorization for high-stakes actions.
In production, this would integrate with external approval workflows.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("HITL")


class HITLGate:
    """
    Human-in-the-Loop authorization gate.
    Requires explicit human approval for sensitive operations.
    """

    # Actions that require human authorization
    HIGH_STAKES_ACTIONS: List[str] = [
        "write_output_file",
        "publish_content",
        "delete_data",
        "external_api_call",
        "send_notification",
    ]

    def __init__(self, auto_approve: bool = False):
        """
        Initialize HITL gate.

        Args:
            auto_approve: If True, automatically approve all requests (for testing).
                          In production, this should be False.
        """
        self.auto_approve = auto_approve
        self.authorization_log: List[Dict[str, Any]] = []

    def requires_authorization(self, action: str) -> bool:
        """
        Check if an action requires human authorization.

        Args:
            action: The action being performed

        Returns:
            True if authorization is required
        """
        return action in self.HIGH_STAKES_ACTIONS

    def request_authorization(
        self, action: str, context: Dict[str, Any], reason: Optional[str] = None
    ) -> bool:
        """
        Request human authorization for an action.

        Args:
            action: The action requiring authorization
            context: Context about the action (what, why, etc.)
            reason: Optional reason for the action

        Returns:
            True if authorized, False if denied
        """
        timestamp = datetime.now().isoformat()

        # Log the request
        request_record = {
            "timestamp": timestamp,
            "action": action,
            "context": context,
            "reason": reason,
            "status": "pending",
        }

        if self.auto_approve:
            logger.info(f"HITL: Auto-approving action '{action}' (test mode)")
            request_record["status"] = "auto_approved"
            self.authorization_log.append(request_record)
            return True

        # Display authorization request to console
        print("\n" + "=" * 60)
        print("🛡️  HUMAN AUTHORIZATION REQUIRED")
        print("=" * 60)
        print(f"Action: {action}")
        print(f"Time: {timestamp}")
        if reason:
            print(f"Reason: {reason}")
        print("\nContext:")
        for key, value in context.items():
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            print(f"  - {key}: {value_str}")
        print("=" * 60)

        # Request approval (console input for demo)
        try:
            response = input("Approve this action? [y/N]: ").strip().lower()
            approved = response in ["y", "yes"]
        except (EOFError, KeyboardInterrupt):
            # Non-interactive mode or interrupted
            logger.warning("HITL: Non-interactive mode, denying by default")
            approved = False

        request_record["status"] = "approved" if approved else "denied"
        self.authorization_log.append(request_record)

        if approved:
            logger.info(f"HITL: Action '{action}' APPROVED by human")
        else:
            logger.warning(f"HITL: Action '{action}' DENIED by human")

        return approved

    def get_authorization_log(self) -> List[Dict[str, Any]]:
        """Get the log of all authorization requests."""
        return self.authorization_log.copy()


# Global HITL gate instance (can be configured per deployment)
_hitl_gate: Optional[HITLGate] = None


def get_hitl_gate(auto_approve: bool = False) -> HITLGate:
    """
    Get the global HITL gate instance.

    Args:
        auto_approve: If True, auto-approve all requests (for testing)

    Returns:
        The HITL gate instance
    """
    global _hitl_gate
    if _hitl_gate is None:
        _hitl_gate = HITLGate(auto_approve=auto_approve)
    return _hitl_gate


def reset_hitl_gate():
    """Reset the global HITL gate (for testing)."""
    global _hitl_gate
    _hitl_gate = None


class CircuitBreaker:
    """
    Automated circuit breaker for agent safety.
    Trips (pauses execution) when failure thresholds are met.
    """

    def __init__(self, error_threshold: int = 5, loop_threshold: int = 3):
        self.error_threshold = error_threshold
        self.loop_threshold = loop_threshold
        self.error_counts: Dict[str, int] = {}
        self.action_history: Dict[str, List[str]] = {}
        self.tripped: bool = False
        self.trip_reason: str = ""

    def record_error(self, agent_id: str):
        """Record an error and check threshold."""
        self.error_counts[agent_id] = self.error_counts.get(agent_id, 0) + 1
        if self.error_counts[agent_id] >= self.error_threshold:
            self.trip(
                f"Error threshold exceeded for {agent_id} ({self.error_counts[agent_id]} errors)"
            )

    def record_action(self, agent_id: str, action: str):
        """Record action and check for looping."""
        history = self.action_history.get(agent_id, [])
        history.append(action)
        self.action_history[agent_id] = history[-10:]  # Keep last 10

        # Check for simple 1-step loop (repeated action)
        if len(history) >= self.loop_threshold:
            recent = history[-self.loop_threshold :]
            if all(a == action for a in recent):
                self.trip(
                    f"Loop detected for {agent_id}: Repeated action '{action}' {self.loop_threshold} times"
                )

    def trip(self, reason: str):
        """Trip the circuit breaker."""
        self.tripped = True
        self.trip_reason = reason
        logger.critical(f"CIRCUIT BREAKER TRIPPED: {reason}")

    def reset(self):
        """Reset the circuit breaker."""
        self.tripped = False
        self.trip_reason = ""
        self.error_counts = {}
        self.action_history = {}
        logger.info("Circuit breaker reset")

    def is_tripped(self) -> bool:
        return self.tripped
