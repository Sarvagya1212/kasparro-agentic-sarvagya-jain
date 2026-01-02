"""
Token Exchange and API Shim for Secure Cross-Domain Access.
Implements:
- RFC 8693 Token Exchange for cross-trust-boundary access
- Managed Connections with explicit authorization policies
- Tamper-proof Shim for secret isolation
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("TokenExchange")


class TokenType(Enum):
    """Types of tokens in the exchange flow."""

    ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
    REFRESH_TOKEN = "urn:ietf:params:oauth:token-type:refresh_token"
    ID_TOKEN = "urn:ietf:params:oauth:token-type:id_token"
    JWT = "urn:ietf:params:oauth:token-type:jwt"
    AGENT_TOKEN = "urn:kasparro:params:token-type:agent"


@dataclass
class TokenExchangeRequest:
    """RFC 8693 Token Exchange Request."""

    grant_type: str = "urn:ietf:params:oauth:grant-type:token-exchange"
    subject_token: str = ""
    subject_token_type: TokenType = TokenType.ACCESS_TOKEN
    requested_token_type: TokenType = TokenType.ACCESS_TOKEN
    audience: str = ""  # Target resource/service
    scope: str = ""
    actor_token: Optional[str] = None
    actor_token_type: Optional[TokenType] = None


@dataclass
class TokenExchangeResponse:
    """RFC 8693 Token Exchange Response."""

    access_token: str
    token_type: str = "Bearer"
    issued_token_type: str = ""
    expires_in: int = 3600
    scope: str = ""
    refresh_token: Optional[str] = None


@dataclass
class ManagedConnection:
    """Defines a managed connection to an external service."""

    connection_id: str
    service_name: str
    authorization_server: str
    allowed_agents: Set[str] = field(default_factory=set)
    allowed_scopes: Set[str] = field(default_factory=set)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)

    def can_access(self, agent_id: str, requested_scopes: Set[str]) -> bool:
        """Check if agent can access with requested scopes."""
        if not self.is_active:
            return False
        if agent_id not in self.allowed_agents and "*" not in self.allowed_agents:
            return False
        if not requested_scopes.issubset(self.allowed_scopes):
            return False
        return True


class TokenExchangeService:
    """
    RFC 8693 Token Exchange Service.
    Enables agents to exchange tokens for cross-domain access.
    """

    def __init__(self, signing_key: str = None):
        self.signing_key = signing_key or secrets.token_urlsafe(32)
        self._connections: Dict[str, ManagedConnection] = {}
        self._exchange_log: List[Dict] = []

    def register_connection(
        self,
        service_name: str,
        authorization_server: str,
        allowed_agents: List[str],
        allowed_scopes: List[str],
    ) -> ManagedConnection:
        """
        Register a managed connection with explicit permissions.
        """
        connection = ManagedConnection(
            connection_id=f"conn_{secrets.token_hex(8)}",
            service_name=service_name,
            authorization_server=authorization_server,
            allowed_agents=set(allowed_agents),
            allowed_scopes=set(allowed_scopes),
        )
        self._connections[connection.connection_id] = connection
        logger.info(
            f"Registered connection: {service_name} "
            f"(agents: {allowed_agents}, scopes: {allowed_scopes})"
        )
        return connection

    def exchange_token(
        self, request: TokenExchangeRequest, agent_id: str, agent_checksum: str
    ) -> TokenExchangeResponse:
        """
        Exchange a subject token for a new token to access target service.
        """
        # Find connection for audience
        connection = self._find_connection(request.audience)
        if not connection:
            raise ValueError(f"No managed connection for audience: {request.audience}")

        # Check permissions
        requested_scopes = set(request.scope.split()) if request.scope else set()
        if not connection.can_access(agent_id, requested_scopes):
            raise PermissionError(
                f"Agent {agent_id} not authorized for {connection.service_name}"
            )

        # Generate new token bound to agent
        new_token = self._mint_token(
            agent_id=agent_id,
            agent_checksum=agent_checksum,
            audience=request.audience,
            scopes=requested_scopes,
        )

        response = TokenExchangeResponse(
            access_token=new_token,
            issued_token_type=TokenType.AGENT_TOKEN.value,
            expires_in=3600,
            scope=" ".join(requested_scopes),
        )

        # Log exchange
        self._log_exchange(agent_id, request.audience, True)

        logger.info(f"Token exchanged for {agent_id} → {request.audience}")
        return response

    def _find_connection(self, audience: str) -> Optional[ManagedConnection]:
        """Find connection matching audience."""
        for conn in self._connections.values():
            if conn.service_name == audience or audience in conn.authorization_server:
                return conn
        return None

    def _mint_token(
        self, agent_id: str, agent_checksum: str, audience: str, scopes: Set[str]
    ) -> str:
        """Mint a new token for the exchange."""
        payload = {
            "agent_id": agent_id,
            "checksum": agent_checksum,
            "aud": audience,
            "scope": list(scopes),
            "iat": time.time(),
            "exp": time.time() + 3600,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

        signature = hmac.new(
            self.signing_key.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()[:32]

        return f"{payload_b64}.{signature}"

    def _log_exchange(self, agent_id: str, audience: str, success: bool):
        """Log token exchange for audit."""
        self._exchange_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
                "audience": audience,
                "success": success,
            }
        )

    def get_exchange_log(self) -> List[Dict]:
        """Get audit log of token exchanges."""
        return self._exchange_log.copy()


class APIShim:
    """
    Tamper-proof shim layer between agent and external APIs.
    Secrets never appear in agent code - only injected at request time.
    """

    def __init__(self, credential_manager=None):
        from skincare_agent_system.security.agent_identity import get_credential_manager

        self.credential_manager = credential_manager or get_credential_manager()
        self._request_log: List[Dict] = []

    def execute_request(
        self,
        agent_id: str,
        endpoint: str,
        method: str = "GET",
        data: Dict = None,
        headers: Dict = None,
    ) -> Dict:
        """
        Execute an API request with automatic credential injection.
        Agent never sees the raw API key.
        """
        # Get credential for agent (not exposed to agent)
        credential = self.credential_manager.get_agent_credential(agent_id)
        if not credential:
            raise ValueError(f"No credential available for agent: {agent_id}")

        # Sign request with PoP
        request_data = f"{method}:{endpoint}:{json.dumps(data or {})}"
        signature = self.credential_manager.sign_agent_request(agent_id, request_data)

        # Prepare headers (inject auth at last moment)
        final_headers = headers.copy() if headers else {}
        final_headers["Authorization"] = f"Bearer {credential}"
        final_headers["X-Agent-ID"] = agent_id
        final_headers["X-Request-Signature"] = signature

        # Log request (without credential)
        self._log_request(agent_id, endpoint, method)

        # In production, execute actual HTTP request here
        # For demo, return success response
        return {
            "status": "success",
            "endpoint": endpoint,
            "method": method,
            "agent": agent_id,
            "signed": True,
        }

    def execute_llm_request(
        self, agent_id: str, prompt: str, model: str = "open-mistral-7b"
    ) -> str:
        """
        Execute LLM request through shim (credential never exposed to agent).
        """
        # Get credential without exposing to agent
        credential = self.credential_manager.get_agent_credential(agent_id)
        if not credential:
            raise ValueError(f"No credential for agent: {agent_id}")

        # Sign request
        request_data = f"llm:{model}:{len(prompt)}"
        self.credential_manager.sign_agent_request(agent_id, request_data)

        # Log request
        self._log_request(agent_id, f"llm:{model}", "POST")

        # Execute LLM call (credential injected only here)
        try:
            from mistralai import Mistral

            client = Mistral(api_key=credential)
            response = client.chat.complete(
                model=model, messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return ""

    def _log_request(self, agent_id: str, endpoint: str, method: str):
        """Log request for audit (no credentials logged)."""
        self._request_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
                "endpoint": endpoint,
                "method": method,
            }
        )

    def get_request_log(self) -> List[Dict]:
        """Get audit log of requests."""
        return self._request_log.copy()


class SecureAPIClient:
    """
    Secure API client that agents use.
    Wraps actual API calls with shim for secret isolation.
    """

    def __init__(self, agent_id: str, shim: APIShim = None):
        self.agent_id = agent_id
        self.shim = shim or APIShim()
        self._token_exchange = TokenExchangeService()

    def request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
        """
        Make an API request (credentials handled by shim).
        """
        return self.shim.execute_request(
            agent_id=self.agent_id, endpoint=endpoint, method=method, data=data
        )

    def generate_content(self, prompt: str) -> str:
        """
        Generate content via LLM (credentials handled by shim).
        """
        return self.shim.execute_llm_request(agent_id=self.agent_id, prompt=prompt)

    def access_external_service(
        self, service_name: str, current_token: str, scopes: List[str]
    ) -> str:
        """
        Get access token for external service via token exchange.
        """
        from skincare_agent_system.security.agent_identity import get_credential_manager

        manager = get_credential_manager()
        identity = manager.get_identity(self.agent_id)

        if not identity:
            raise ValueError(f"No identity for agent: {self.agent_id}")

        request = TokenExchangeRequest(
            subject_token=current_token, audience=service_name, scope=" ".join(scopes)
        )

        response = self._token_exchange.exchange_token(
            request=request, agent_id=self.agent_id, agent_checksum=identity.checksum
        )

        return response.access_token


# Singleton shim instance
_api_shim: Optional[APIShim] = None


def get_api_shim() -> APIShim:
    """Get singleton API shim."""
    global _api_shim
    if _api_shim is None:
        _api_shim = APIShim()
    return _api_shim


def create_secure_client(agent_id: str) -> SecureAPIClient:
    """Create a secure API client for an agent."""
    return SecureAPIClient(agent_id=agent_id, shim=get_api_shim())
