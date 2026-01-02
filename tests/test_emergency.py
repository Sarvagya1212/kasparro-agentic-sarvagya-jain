"""
Tests for Emergency Controls and Fine-Grained Authorization.
Run with: pytest tests/test_emergency.py -v
"""

import time

import pytest

from skincare_agent_system.security.emergency_controls import (
    AgentPermissions,
    BehavioralMonitor,
    BehaviorProfile,
    EmergencyController,
    FineGrainedAuth,
    Scope,
)


class TestScope:
    """Tests for scope matching."""

    def test_scope_string(self):
        """Should format scope as MCP string."""
        scope = Scope(resource="crm", action="read")
        assert str(scope) == "mcp:crm:read"

    def test_scope_matches(self):
        """Should match resource and action."""
        scope = Scope(resource="crm", action="read")
        assert scope.matches("crm", "read") is True
        assert scope.matches("crm", "write") is False


class TestAgentPermissions:
    """Tests for agent permissions."""

    def test_has_scope_granted(self):
        """Should allow granted scopes."""
        perms = AgentPermissions(
            agent_id="agent_1", scopes=[Scope("crm", "read"), Scope("crm", "write")]
        )
        assert perms.has_scope("crm", "read") is True
        assert perms.has_scope("crm", "write") is True

    def test_has_scope_not_granted(self):
        """Should deny non-granted scopes."""
        perms = AgentPermissions(agent_id="agent_1", scopes=[Scope("crm", "read")])
        assert perms.has_scope("crm", "delete") is False

    def test_denied_overrides_grant(self):
        """Denied scopes should override grants."""
        perms = AgentPermissions(
            agent_id="agent_1",
            scopes=[Scope("crm", "read"), Scope("crm", "write")],
            denied_scopes=[Scope("crm", "write")],
        )
        assert perms.has_scope("crm", "read") is True
        assert perms.has_scope("crm", "write") is False

    def test_inactive_denies_all(self):
        """Inactive agent should deny all."""
        perms = AgentPermissions(
            agent_id="agent_1", scopes=[Scope("crm", "read")], is_active=False
        )
        assert perms.has_scope("crm", "read") is False

    def test_expired_denies_all(self):
        """Expired permissions should deny all."""
        perms = AgentPermissions(
            agent_id="agent_1",
            scopes=[Scope("crm", "read")],
            expires_at=time.time() - 100,  # Expired
        )
        assert perms.has_scope("crm", "read") is False


class TestFineGrainedAuth:
    """Tests for fine-grained authorization."""

    def test_grant_permission(self):
        """Should grant fine-grained permissions."""
        fga = FineGrainedAuth()

        fga.grant_permission("agent_1", "documents", "read")

        assert fga.check_permission("agent_1", "documents", "read") is True

    def test_deny_permission(self):
        """Should deny explicitly denied permissions."""
        fga = FineGrainedAuth()

        fga.grant_permission("agent_1", "documents", "read")
        fga.grant_permission("agent_1", "documents", "write")
        fga.deny_permission("agent_1", "documents", "write")

        assert fga.check_permission("agent_1", "documents", "read") is True
        assert fga.check_permission("agent_1", "documents", "write") is False

    def test_filter_data(self):
        """Should filter data based on scope filters."""
        fga = FineGrainedAuth()

        fga.grant_permission(
            "agent_1", "documents", "read", filters={"department": "sales"}
        )

        data = [
            {"id": 1, "department": "sales", "content": "Sales doc"},
            {"id": 2, "department": "hr", "content": "HR doc"},
            {"id": 3, "department": "sales", "content": "Another sales"},
        ]

        filtered = fga.filter_data("agent_1", data, "documents")

        assert len(filtered) == 2
        assert all(d["department"] == "sales" for d in filtered)


class TestBehavioralMonitor:
    """Tests for behavioral monitoring."""

    def test_record_request(self):
        """Should record agent requests."""
        monitor = BehavioralMonitor()
        monitor.set_baseline("agent_1")

        monitor.record_request("agent_1", "api")

        activity = monitor._activity["agent_1"]
        assert len(activity.request_timestamps) == 1

    def test_detect_high_request_rate(self):
        """Should detect high request rate anomaly."""
        monitor = BehavioralMonitor()
        monitor.set_baseline("agent_1", avg_requests=5.0)

        # Generate many requests
        for _ in range(50):
            monitor.record_request("agent_1")

        anomalies = monitor.check_anomalies("agent_1")

        assert len(anomalies) > 0
        assert "request rate" in anomalies[0].lower()

    def test_detect_unusual_resource(self):
        """Should detect unusual resource access."""
        monitor = BehavioralMonitor()
        monitor.set_baseline("agent_1", typical_resources={"documents", "api"})

        monitor.record_request("agent_1", "secrets")

        anomalies = monitor.check_anomalies("agent_1")

        assert len(anomalies) > 0

    def test_record_alert(self):
        """Should record alerts."""
        monitor = BehavioralMonitor()
        monitor.set_baseline("agent_1", avg_requests=1.0)

        for _ in range(10):
            monitor.record_request("agent_1")

        monitor.check_anomalies("agent_1")

        alerts = monitor.get_alerts()
        assert len(alerts) > 0


class TestEmergencyController:
    """Tests for emergency controls."""

    def test_universal_logout(self):
        """Should revoke all access for an agent."""
        fga = FineGrainedAuth()
        fga.grant_permission("agent_1", "api", "read")

        controller = EmergencyController(fga=fga)

        assert controller.is_agent_active("agent_1") is True

        controller.universal_logout("agent_1", "Suspicious activity")

        assert controller.is_agent_active("agent_1") is False

    def test_global_lockdown(self):
        """Should lock down all agents."""
        fga = FineGrainedAuth()
        fga.grant_permission("agent_1", "api", "read")
        fga.grant_permission("agent_2", "api", "read")

        controller = EmergencyController(fga=fga)

        controller.global_lockdown("Critical threat")

        assert controller.is_agent_active("agent_1") is False
        assert controller.is_agent_active("agent_2") is False

    def test_lift_lockdown(self):
        """Should lift lockdown for agent."""
        fga = FineGrainedAuth()
        fga.grant_permission("agent_1", "api", "read")

        controller = EmergencyController(fga=fga)
        controller.universal_logout("agent_1", "Test")

        assert controller.is_agent_active("agent_1") is False

        controller.lift_lockdown("agent_1")

        assert controller.is_agent_active("agent_1") is True

    def test_auto_lockdown(self):
        """Should auto-lockdown on multiple anomalies."""
        fga = FineGrainedAuth()
        fga.grant_permission("agent_1", "api", "read")

        monitor = BehavioralMonitor()
        monitor.set_baseline("agent_1", avg_requests=1.0, typical_resources={"api"})

        controller = EmergencyController(fga=fga, monitor=monitor)

        # Generate anomalies
        for _ in range(50):
            monitor.record_request("agent_1", "secrets")

        locked = controller.auto_lockdown_check("agent_1")

        assert locked is True
        assert controller.is_agent_active("agent_1") is False

    def test_lockdown_log(self):
        """Should log all lockdown events."""
        controller = EmergencyController()

        controller.universal_logout("agent_1", "Test logout")
        controller.global_lockdown("Test lockdown")

        log = controller.get_lockdown_log()

        assert len(log) == 2
        assert log[0]["action"] == "UNIVERSAL_LOGOUT"
        assert log[1]["action"] == "GLOBAL_LOCKDOWN"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
