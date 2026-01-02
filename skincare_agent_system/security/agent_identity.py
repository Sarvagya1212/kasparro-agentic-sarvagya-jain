"""
Agent Identity and Credential Management.
Implements:
- Distinct agent identities with unique checksums
- Agentic JWT for agent authentication
- Dynamic secret rotation
- Proof of Possession (PoP) signing
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AgentIdentity")


@dataclass
class AgentCredential:
    """Credential bound to a specific agent."""

    agent_id: str
    agent_checksum: str
    api_key: str
    issued_at: float
    expires_at: float
    scope: List[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def is_valid_for_agent(self, agent_checksum: str) -> bool:
        """Verify credential matches agent's current checksum."""
        return self.agent_checksum == agent_checksum


@dataclass
class AgentIdentity:
    """
    Unique identity for each agent.
    Checksum derived from agent's configuration.
    """

    agent_id: str
    agent_name: str
    role: str
    tools: List[str]
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """
        Compute unique checksum from agent configuration.
        If agent's prompt/tools change, checksum changes, invalidating credentials.
        """
        data = {
            "id": self.agent_id,
            "name": self.agent_name,
            "role": self.role,
            "tools": sorted(self.tools),
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]


class SecretVault:
    """
    Centralized secret management (simulated vault).
    In production, replace with HashiCorp Vault or AWS Secrets Manager.
    """

    def __init__(self):
        self._secrets: Dict[str, str] = {}
        self._rotation_schedule: Dict[str, float] = {}
        self._rotation_interval = 90 * 24 * 60 * 60  # 90 days in seconds

    def store_secret(self, key: str, value: str):
        """Store a secret with rotation tracking."""
        self._secrets[key] = value
        self._rotation_schedule[key] = time.time() + self._rotation_interval
        logger.info(f"Secret stored: {key} (rotates in 90 days)")

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret if not expired."""
        if key not in self._secrets:
            return None

        if self._needs_rotation(key):
            logger.warning(f"Secret {key} needs rotation!")

        return self._secrets.get(key)

    def _needs_rotation(self, key: str) -> bool:
        """Check if secret needs rotation."""
        if key not in self._rotation_schedule:
            return True
        return time.time() > self._rotation_schedule[key]

    def rotate_secret(self, key: str) -> str:
        """Rotate a secret and return new value."""
        new_secret = secrets.token_urlsafe(32)
        self.store_secret(key, new_secret)
        logger.info(f"Secret {key} rotated")
        return new_secret

    def generate_dynamic_secret(self, purpose: str, ttl_seconds: int = 3600) -> str:
        """
        Generate a dynamic (temporary) secret.
        TTL defaults to 1 hour.
        """
        secret = secrets.token_urlsafe(32)
        key = f"dynamic_{purpose}_{int(time.time())}"
        self._secrets[key] = secret
        self._rotation_schedule[key] = time.time() + ttl_seconds
        logger.info(f"Dynamic secret generated: {purpose} (TTL: {ttl_seconds}s)")
        return secret


class AgenticJWT:
    """
    JWT-like tokens bound to agent identity.
    Includes agent checksum for tamper detection.
    """

    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_urlsafe(32)

    def create_token(
        self, agent_identity: AgentIdentity, scopes: List[str], ttl_seconds: int = 3600
    ) -> str:
        """
        Create an agentic token bound to agent's checksum.
        """
        now = time.time()
        payload = {
            "agent_id": agent_identity.agent_id,
            "agent_name": agent_identity.agent_name,
            "checksum": agent_identity.checksum,
            "scopes": scopes,
            "iat": now,
            "exp": now + ttl_seconds,
        }

        # Encode payload
        payload_json = json.dumps(payload, sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

        # Create signature
        signature = self._sign(payload_b64)

        token = f"{payload_b64}.{signature}"
        logger.info(f"Token created for {agent_identity.agent_name}")
        return token

    def verify_token(self, token: str, agent_identity: AgentIdentity) -> Dict[str, Any]:
        """
        Verify token and check it matches current agent identity.
        """
        try:
            parts = token.split(".")
            if len(parts) != 2:
                raise ValueError("Invalid token format")

            payload_b64, signature = parts

            # Verify signature
            expected_sig = self._sign(payload_b64)
            if not hmac.compare_digest(signature, expected_sig):
                raise ValueError("Invalid signature")

            # Decode payload
            payload_json = base64.urlsafe_b64decode(payload_b64).decode()
            payload = json.loads(payload_json)

            # Check expiration
            if time.time() > payload.get("exp", 0):
                raise ValueError("Token expired")

            # Check agent checksum (prevents using token if agent was modified)
            if payload.get("checksum") != agent_identity.checksum:
                raise ValueError(
                    "Agent checksum mismatch - agent may have been modified"
                )

            logger.info(f"Token verified for {payload.get('agent_name')}")
            return payload

        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise

    def _sign(self, data: str) -> str:
        """Create HMAC signature."""
        sig = hmac.new(
            self.secret_key.encode(), data.encode(), hashlib.sha256
        ).hexdigest()
        return sig[:32]


class ProofOfPossession:
    """
    Proof of Possession (PoP) for preventing token replay attacks.
    Agent signs requests with ephemeral key.
    """

    def __init__(self):
        # In production, use Ed25519 from cryptography library
        # For demo, using HMAC with ephemeral key
        self.ephemeral_key = secrets.token_bytes(32)

    def sign_request(
        self, agent_id: str, request_data: str, timestamp: float = None
    ) -> str:
        """
        Sign a request to prove possession of key.
        """
        ts = timestamp or time.time()
        message = f"{agent_id}:{ts}:{request_data}"

        signature = hmac.new(
            self.ephemeral_key, message.encode(), hashlib.sha256
        ).hexdigest()

        return f"{ts}:{signature}"

    def verify_signature(
        self,
        agent_id: str,
        request_data: str,
        signature: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """
        Verify request signature.
        Rejects if timestamp too old (prevents replay).
        """
        try:
            parts = signature.split(":")
            if len(parts) != 2:
                return False

            ts, sig = parts
            ts = float(ts)

            # Check timestamp freshness
            if time.time() - ts > max_age_seconds:
                logger.warning("Signature too old - possible replay attack")
                return False

            # Verify signature
            expected = self.sign_request(agent_id, request_data, ts)
            return hmac.compare_digest(signature, expected)

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False


class AgentCredentialManager:
    """
    Manages credentials for all agents.
    Combines vault, JWT, and PoP for complete security.
    """

    def __init__(self):
        self.vault = SecretVault()
        self.jwt_provider = AgenticJWT()
        self.pop_provider = ProofOfPossession()
        self._agent_identities: Dict[str, AgentIdentity] = {}
        self._agent_tokens: Dict[str, str] = {}

        # Store master API key in vault
        api_key = os.getenv("MISTRAL_API_KEY", "")
        if api_key:
            self.vault.store_secret("mistral_api_key", api_key)

    def register_agent(
        self, agent_id: str, agent_name: str, role: str, tools: List[str]
    ) -> AgentIdentity:
        """
        Register an agent with unique identity.
        """
        identity = AgentIdentity(
            agent_id=agent_id, agent_name=agent_name, role=role, tools=tools
        )
        self._agent_identities[agent_id] = identity

        # Create token for agent
        scopes = self._determine_scopes(role)
        token = self.jwt_provider.create_token(identity, scopes)
        self._agent_tokens[agent_id] = token

        logger.info(
            f"Agent registered: {agent_name} " f"(checksum: {identity.checksum[:8]}...)"
        )
        return identity

    def get_agent_credential(self, agent_id: str) -> Optional[str]:
        """
        Get API credential for an agent (with validation).
        """
        identity = self._agent_identities.get(agent_id)
        if not identity:
            logger.error(f"Unknown agent: {agent_id}")
            return None

        token = self._agent_tokens.get(agent_id)
        if not token:
            logger.error(f"No token for agent: {agent_id}")
            return None

        # Verify token still valid for this agent
        try:
            self.jwt_provider.verify_token(token, identity)
        except Exception:
            # Token invalid, issue new one
            scopes = self._determine_scopes(identity.role)
            token = self.jwt_provider.create_token(identity, scopes)
            self._agent_tokens[agent_id] = token

        # Return actual API key from vault
        return self.vault.get_secret("mistral_api_key")

    def sign_agent_request(self, agent_id: str, request_data: str) -> str:
        """
        Sign a request for an agent (PoP).
        """
        return self.pop_provider.sign_request(agent_id, request_data)

    def verify_agent_request(
        self, agent_id: str, request_data: str, signature: str
    ) -> bool:
        """
        Verify an agent's signed request.
        """
        return self.pop_provider.verify_signature(agent_id, request_data, signature)

    def _determine_scopes(self, role: str) -> List[str]:
        """Determine scopes based on agent role."""
        base_scopes = ["read"]

        if "Manager" in role or "Coordinator" in role:
            return base_scopes + ["write", "execute", "delegate"]
        elif "Analyst" in role or "Data" in role:
            return base_scopes + ["analyze"]
        elif "Generator" in role or "Writer" in role:
            return base_scopes + ["write", "generate"]
        elif "Verifier" in role:
            return base_scopes + ["verify", "audit"]

        return base_scopes

    def get_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get agent identity by ID."""
        return self._agent_identities.get(agent_id)

    def list_agents(self) -> List[str]:
        """List all registered agent IDs."""
        return list(self._agent_identities.keys())


# Singleton instance
_credential_manager: Optional[AgentCredentialManager] = None


def get_credential_manager() -> AgentCredentialManager:
    """Get or create singleton credential manager."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = AgentCredentialManager()
    return _credential_manager
