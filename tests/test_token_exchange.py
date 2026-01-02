"""
Tests for Token Exchange and API Shim.
Run with: pytest tests/test_token_exchange.py -v
"""

import time

import pytest

from skincare_agent_system.security.agent_identity import AgentCredentialManager
from skincare_agent_system.security.token_exchange import (
    APIShim,
    ManagedConnection,
    SecureAPIClient,
    TokenExchangeRequest,
    TokenExchangeResponse,
    TokenExchangeService,
    TokenType,
)


class TestManagedConnection:
    """Tests for managed connections."""

    def test_can_access_allowed_agent(self):
        """Should allow access for authorized agents."""
        conn = ManagedConnection(
            connection_id="conn_1",
            service_name="test_service",
            authorization_server="https://auth.example.com",
            allowed_agents={"agent_1", "agent_2"},
            allowed_scopes={"read", "write"},
        )

        assert conn.can_access("agent_1", {"read"}) is True
        assert conn.can_access("agent_1", {"read", "write"}) is True

    def test_deny_unauthorized_agent(self):
        """Should deny access for unauthorized agents."""
        conn = ManagedConnection(
            connection_id="conn_1",
            service_name="test_service",
            authorization_server="https://auth.example.com",
            allowed_agents={"agent_1"},
            allowed_scopes={"read"},
        )

        assert conn.can_access("agent_3", {"read"}) is False

    def test_deny_unauthorized_scope(self):
        """Should deny access for unauthorized scopes."""
        conn = ManagedConnection(
            connection_id="conn_1",
            service_name="test_service",
            authorization_server="https://auth.example.com",
            allowed_agents={"agent_1"},
            allowed_scopes={"read"},
        )

        assert conn.can_access("agent_1", {"read", "write"}) is False

    def test_wildcard_agent_access(self):
        """Should allow wildcard agent access."""
        conn = ManagedConnection(
            connection_id="conn_1",
            service_name="test_service",
            authorization_server="https://auth.example.com",
            allowed_agents={"*"},
            allowed_scopes={"read"},
        )

        assert conn.can_access("any_agent", {"read"}) is True

    def test_inactive_connection_denied(self):
        """Should deny access to inactive connections."""
        conn = ManagedConnection(
            connection_id="conn_1",
            service_name="test_service",
            authorization_server="https://auth.example.com",
            allowed_agents={"agent_1"},
            allowed_scopes={"read"},
            is_active=False,
        )

        assert conn.can_access("agent_1", {"read"}) is False


class TestTokenExchangeService:
    """Tests for token exchange service."""

    def test_register_connection(self):
        """Should register managed connections."""
        service = TokenExchangeService()

        conn = service.register_connection(
            service_name="pricing_db",
            authorization_server="https://auth.pricing.com",
            allowed_agents=["sales_agent"],
            allowed_scopes=["read_prices"],
        )

        assert conn.service_name == "pricing_db"
        assert "sales_agent" in conn.allowed_agents

    def test_exchange_token_success(self):
        """Should exchange token for authorized agent."""
        service = TokenExchangeService()

        service.register_connection(
            service_name="pricing_db",
            authorization_server="https://auth.pricing.com",
            allowed_agents=["agent_1"],
            allowed_scopes=["read"],
        )

        request = TokenExchangeRequest(
            subject_token="original_token", audience="pricing_db", scope="read"
        )

        response = service.exchange_token(
            request=request, agent_id="agent_1", agent_checksum="checksum_123"
        )

        assert response.access_token is not None
        assert response.expires_in == 3600

    def test_exchange_token_unauthorized(self):
        """Should reject unauthorized exchange."""
        service = TokenExchangeService()

        service.register_connection(
            service_name="pricing_db",
            authorization_server="https://auth.pricing.com",
            allowed_agents=["agent_1"],
            allowed_scopes=["read"],
        )

        request = TokenExchangeRequest(
            subject_token="original_token", audience="pricing_db", scope="read"
        )

        with pytest.raises(PermissionError):
            service.exchange_token(
                request=request,
                agent_id="unauthorized_agent",
                agent_checksum="checksum",
            )

    def test_exchange_log(self):
        """Should log token exchanges."""
        service = TokenExchangeService()

        service.register_connection(
            service_name="test_service",
            authorization_server="https://auth.test.com",
            allowed_agents=["agent_1"],
            allowed_scopes=["read"],
        )

        request = TokenExchangeRequest(
            subject_token="token", audience="test_service", scope="read"
        )

        service.exchange_token(request, "agent_1", "checksum")

        log = service.get_exchange_log()
        assert len(log) == 1
        assert log[0]["agent_id"] == "agent_1"


class TestAPIShim:
    """Tests for API shim."""

    def test_execute_request(self):
        """Should execute request with credential injection."""
        # Create credential manager with test agent
        manager = AgentCredentialManager()
        manager.register_agent("agent_1", "TestAgent", "Tester", [])
        # Store test API key in vault
        manager.vault.store_secret("mistral_api_key", "test_key_12345")

        shim = APIShim(credential_manager=manager)

        result = shim.execute_request(
            agent_id="agent_1", endpoint="https://api.example.com/data", method="GET"
        )

        assert result["status"] == "success"
        assert result["signed"] is True

    def test_request_log(self):
        """Should log requests for audit."""
        manager = AgentCredentialManager()
        manager.register_agent("agent_1", "TestAgent", "Tester", [])
        manager.vault.store_secret("mistral_api_key", "test_key_12345")

        shim = APIShim(credential_manager=manager)
        shim.execute_request("agent_1", "https://api.example.com", "GET")

        log = shim.get_request_log()
        assert len(log) == 1
        assert log[0]["agent_id"] == "agent_1"


class TestSecureAPIClient:
    """Tests for secure API client."""

    def test_request(self):
        """Should make request through shim."""
        manager = AgentCredentialManager()
        manager.register_agent("agent_1", "TestAgent", "Tester", [])
        manager.vault.store_secret("mistral_api_key", "test_key_12345")

        shim = APIShim(credential_manager=manager)
        client = SecureAPIClient(agent_id="agent_1", shim=shim)

        result = client.request("/api/test", method="POST", data={"key": "value"})

        assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
