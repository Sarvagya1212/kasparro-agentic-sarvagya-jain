"""
Tests for Agent Identity and Credential Management.
Run with: pytest tests/test_identity.py -v
"""

import time

import pytest

from skincare_agent_system.security.agent_identity import (
    AgentCredentialManager,
    AgenticJWT,
    AgentIdentity,
    ProofOfPossession,
    SecretVault,
)


class TestAgentIdentity:
    """Tests for agent identity checksum."""

    def test_checksum_deterministic(self):
        """Same config should produce same checksum."""
        id1 = AgentIdentity(
            agent_id="agent_1",
            agent_name="TestAgent",
            role="Tester",
            tools=["test_tool"],
        )
        id2 = AgentIdentity(
            agent_id="agent_1",
            agent_name="TestAgent",
            role="Tester",
            tools=["test_tool"],
        )
        assert id1.checksum == id2.checksum

    def test_checksum_changes_with_config(self):
        """Different config should produce different checksum."""
        id1 = AgentIdentity(
            agent_id="agent_1",
            agent_name="TestAgent",
            role="Tester",
            tools=["test_tool"],
        )
        id2 = AgentIdentity(
            agent_id="agent_1",
            agent_name="TestAgent",
            role="Tester",
            tools=["different_tool"],  # Changed
        )
        assert id1.checksum != id2.checksum


class TestSecretVault:
    """Tests for secret vault."""

    def test_store_and_retrieve(self):
        """Should store and retrieve secrets."""
        vault = SecretVault()
        vault.store_secret("test_key", "test_value")

        assert vault.get_secret("test_key") == "test_value"

    def test_missing_secret_returns_none(self):
        """Should return None for missing secrets."""
        vault = SecretVault()
        assert vault.get_secret("nonexistent") is None

    def test_rotate_secret(self):
        """Should rotate secrets."""
        vault = SecretVault()
        vault.store_secret("rotate_me", "old_value")

        new_value = vault.rotate_secret("rotate_me")

        assert new_value != "old_value"
        assert vault.get_secret("rotate_me") == new_value

    def test_dynamic_secret(self):
        """Should generate dynamic secrets."""
        vault = SecretVault()
        secret = vault.generate_dynamic_secret("test_purpose", ttl_seconds=3600)

        assert secret is not None
        assert len(secret) > 16


class TestAgenticJWT:
    """Tests for agentic JWT tokens."""

    def test_create_and_verify_token(self):
        """Should create and verify tokens."""
        jwt = AgenticJWT(secret_key="test_secret")
        identity = AgentIdentity(
            agent_id="agent_1", agent_name="TestAgent", role="Tester", tools=[]
        )

        token = jwt.create_token(identity, scopes=["read"])
        payload = jwt.verify_token(token, identity)

        assert payload["agent_id"] == "agent_1"
        assert payload["checksum"] == identity.checksum
        assert "read" in payload["scopes"]

    def test_reject_tampered_token(self):
        """Should reject tokens with wrong signature."""
        jwt = AgenticJWT(secret_key="test_secret")
        identity = AgentIdentity(
            agent_id="agent_1", agent_name="TestAgent", role="Tester", tools=[]
        )

        token = jwt.create_token(identity, scopes=["read"])
        tampered = token + "tampered"

        with pytest.raises(ValueError):
            jwt.verify_token(tampered, identity)

    def test_reject_modified_agent(self):
        """Should reject token if agent was modified."""
        jwt = AgenticJWT(secret_key="test_secret")

        original_identity = AgentIdentity(
            agent_id="agent_1", agent_name="TestAgent", role="Tester", tools=["tool_a"]
        )

        # Create token with original identity
        token = jwt.create_token(original_identity, scopes=["read"])

        # Modify agent (different tools = different checksum)
        modified_identity = AgentIdentity(
            agent_id="agent_1",
            agent_name="TestAgent",
            role="Tester",
            tools=["tool_b"],  # Changed!
        )

        # Verification should fail
        with pytest.raises(ValueError, match="checksum mismatch"):
            jwt.verify_token(token, modified_identity)


class TestProofOfPossession:
    """Tests for PoP signing."""

    def test_sign_and_verify(self):
        """Should sign and verify requests."""
        pop = ProofOfPossession()

        signature = pop.sign_request("agent_1", "request_data")
        is_valid = pop.verify_signature("agent_1", "request_data", signature)

        assert is_valid is True

    def test_reject_wrong_data(self):
        """Should reject signature for wrong data."""
        pop = ProofOfPossession()

        signature = pop.sign_request("agent_1", "original_data")
        is_valid = pop.verify_signature("agent_1", "modified_data", signature)

        assert is_valid is False

    def test_reject_old_signature(self):
        """Should reject old signatures (replay attack prevention)."""
        pop = ProofOfPossession()

        # Create old signature
        old_timestamp = time.time() - 600  # 10 minutes ago
        signature = pop.sign_request("agent_1", "data", timestamp=old_timestamp)

        # Should be rejected as too old
        is_valid = pop.verify_signature(
            "agent_1", "data", signature, max_age_seconds=300
        )

        assert is_valid is False


class TestAgentCredentialManager:
    """Tests for credential manager."""

    def test_register_agent(self):
        """Should register agents with unique identities."""
        manager = AgentCredentialManager()

        identity = manager.register_agent(
            agent_id="test_agent",
            agent_name="TestAgent",
            role="Tester",
            tools=["test_tool"],
        )

        assert identity is not None
        assert identity.checksum is not None
        assert "test_agent" in manager.list_agents()

    def test_get_identity(self):
        """Should retrieve agent identity."""
        manager = AgentCredentialManager()
        manager.register_agent("agent_1", "Agent1", "Role1", [])

        identity = manager.get_identity("agent_1")

        assert identity is not None
        assert identity.agent_name == "Agent1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
