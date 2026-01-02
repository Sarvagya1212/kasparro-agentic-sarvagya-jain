"""
LLM Client: Unified interface for Mistral 7B (via Mistral API).
Provides text generation and structured JSON output.

Security: Uses CredentialShim pattern - agents pass identity, never see API keys.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("LLMClient")

# Try to import mistralai
try:
    from mistralai import Mistral

    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    logger.warning("mistralai not installed. Run: pip install mistralai")


class LLMClient:
    """
    Unified LLM client for Mistral 7B.

    Security: Uses CredentialShim pattern.
    - Agents pass their identity, NOT API keys
    - Credentials are injected at network layer by the shim
    - Agents never see raw API keys
    """

    def __init__(self, model: str = "open-mistral-7b"):
        """
        Initialize Mistral client with secure credential handling.

        Args:
            model: Model name (default: open-mistral-7b)
        """
        self.model_name = model
        self._client = None
        self._configured = False

        if not MISTRAL_AVAILABLE:
            raise ImportError("mistralai not installed. Run: pip install mistralai")

        logger.info(
            f"LLM Client initialized with {self.model_name} (using CredentialShim)"
        )

    def _ensure_configured(self, agent_identity: str = None):
        """
        Configure Mistral with credentials from shim.

        This is called lazily when first generation is requested.
        Credentials are injected via the shim - never exposed to agents.
        """
        # Mistral Client can be lightweight, but we might want to re-init if identity changes?
        # Typically one client per request in this stateless wrapper, or cache it.
        # Since 'api_key' is passed to Mistral constructor, we create a new client or cache one if key is same.
        # But Shim might return different keys for different agents (e.g. dynamic secrets).
        # So it's safer to re-create client or check key.

        from skincare_agent_system.security.credential_shim import get_credential_shim

        shim = get_credential_shim()

        # Use provided identity or fallback to system identity
        identity = agent_identity or "agent_system"

        # Shim injects credential - agent never sees it
        api_key = shim.get_credential_for_agent(identity)

        # Always re-init client to ensure correct key is used (especially for dynamic secrets)
        self._client = Mistral(api_key=api_key)
        self._configured = True

        logger.debug(f"Mistral configured via shim for: {identity}")

    def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        agent_identity: str = None,
    ) -> str:
        """
        Generate text completion.

        Args:
            prompt: User prompt
            system: Optional system instruction
            temperature: Creativity (0-1)
            max_tokens: Max response length (Mistral uses max_tokens)
            agent_identity: Agent identity for credential injection

        Returns:
            Generated text
        """
        try:
            # Check kill switch via monitor
            self._check_agent_allowed(agent_identity)

            # Configure via shim (credentials injected here, never exposed)
            self._ensure_configured(agent_identity)

            # Build messages
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Generate
            response = self._client.chat.complete(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens if max_tokens else None,
            )

            result = response.choices[0].message.content.strip()

            # Record usage for monitoring (estimate tokens)
            self._record_usage(agent_identity, len(result) // 4)

            logger.debug(f"Generated {len(result)} chars")
            return result

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _check_agent_allowed(self, agent_identity: str):
        """Check if agent is allowed via monitor (kill switch check)."""
        try:
            from skincare_agent_system.infrastructure.agent_monitor import (
                get_agent_monitor,
            )

            monitor = get_agent_monitor()
            if not monitor.is_agent_allowed(agent_identity or "agent_system"):
                raise PermissionError(
                    f"Agent access denied: {agent_identity} (revoked or suspended)"
                )
        except ImportError:
            pass  # Monitor not available

    def _record_usage(self, agent_identity: str, estimated_tokens: int):
        """Record usage for monitoring and anomaly detection."""
        try:
            from skincare_agent_system.infrastructure.agent_monitor import (
                get_agent_monitor,
            )

            monitor = get_agent_monitor()
            monitor.record_usage(agent_identity or "agent_system", estimated_tokens)
        except ImportError:
            pass  # Monitor not available

    def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any] = None,
        system: str = None,
        temperature: float = 0.3,
        agent_identity: str = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: User prompt (should request JSON output)
            schema: Expected JSON schema (for documentation)
            system: Optional system instruction
            temperature: Lower for more consistent JSON
            agent_identity: Agent identity for credential injection

        Returns:
            Parsed JSON dict
        """
        # Add JSON instruction
        json_prompt = f"""{prompt}

IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation."""

        if schema:
            json_prompt += f"\n\nExpected schema: {json.dumps(schema, indent=2)}"

        # Use generate with response_format={"type": "json_object"} if available,
        # but manual instruction is safer for general 7B models unless specifically instructed.
        # Mistral API supports response_format, but python client usage varies.
        # We'll stick to text generation + parsing for compatibility with open-mistral-7b.

        response = self.generate(
            json_prompt,
            system=system,
            temperature=temperature,
            agent_identity=agent_identity,
        )

        # Extract JSON from response
        return self._parse_json(response)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON from: {text[:200]}")
        raise ValueError(f"Could not parse JSON from LLM response: {text[:100]}...")

    def is_available(self) -> bool:
        """Check if LLM is properly configured."""
        return MISTRAL_AVAILABLE


# Singleton instance for easy access
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create singleton LLM client."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def set_llm_client(client: LLMClient):
    """Set custom LLM client (for testing)."""
    global _client
    _client = client
