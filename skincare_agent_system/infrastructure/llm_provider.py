"""
LLM Provider: Abstraction layer for multiple LLM backends.
Supports OpenAI, Anthropic, Mistral with caching and fallback.
"""

import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("LLMProvider")


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    cached: bool = False
    latency_ms: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class CacheEntry:
    """Cached LLM response."""
    response: LLMResponse
    timestamp: str
    hits: int = 0
    ttl_seconds: float = 3600.0  # 1 hour default

    def is_expired(self) -> bool:
        created = datetime.fromisoformat(self.timestamp)
        return datetime.now() > created + timedelta(seconds=self.ttl_seconds)


class LLMCache:
    """
    In-memory cache for LLM responses.
    """

    def __init__(self, max_entries: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    def _compute_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        system: Optional[str] = None
    ) -> str:
        """Compute cache key from request parameters."""
        key_data = f"{prompt}|{model}|{temperature}|{system or ''}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get(
        self,
        prompt: str,
        model: str,
        temperature: float,
        system: Optional[str] = None
    ) -> Optional[LLMResponse]:
        """Get cached response if available and not expired."""
        key = self._compute_key(prompt, model, temperature, system)
        entry = self._cache.get(key)

        if entry:
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            entry.hits += 1
            self._hits += 1
            response = entry.response
            response.cached = True
            return response

        self._misses += 1
        return None

    def put(
        self,
        prompt: str,
        model: str,
        temperature: float,
        response: LLMResponse,
        system: Optional[str] = None,
        ttl_seconds: float = 3600.0
    ) -> None:
        """Cache a response."""
        key = self._compute_key(prompt, model, temperature, system)

        self._cache[key] = CacheEntry(
            response=response,
            timestamp=datetime.now().isoformat(),
            ttl_seconds=ttl_seconds
        )

        # Prune if too many entries
        if len(self._cache) > self._max_entries:
            self._prune()

    def _prune(self) -> None:
        """Remove expired and least-used entries."""
        # Remove expired
        expired = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired:
            del self._cache[k]

        # Remove least used if still too many
        if len(self._cache) > self._max_entries:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].hits
            )
            to_remove = len(self._cache) - self._max_entries // 2
            for k, _ in sorted_entries[:to_remove]:
                del self._cache[k]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate
        }


class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate text completion."""
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON response."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        pass


class MistralProvider(BaseLLMProvider):
    """Mistral AI provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "open-mistral-7b"):
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None and self._api_key:
            try:
                from mistralai import Mistral
                self._client = Mistral(api_key=self._api_key)
            except ImportError:
                logger.warning("Mistral SDK not installed")
        return self._client

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        client = self._get_client()
        if not client:
            return LLMResponse(
                content="",
                model=self._model,
                provider=self.provider_name
            )

        start_time = time.time()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.complete(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0

            return LLMResponse(
                content=content,
                model=self._model,
                provider=self.provider_name,
                tokens_used=tokens,
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            logger.error(f"Mistral generation failed: {e}")
            return LLMResponse(
                content="",
                model=self._model,
                provider=self.provider_name
            )

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        json_prompt = f"{prompt}\n\nRespond only with valid JSON, no other text."
        if system:
            system = f"{system}\nYou must respond with valid JSON only."

        response = self.generate(json_prompt, system, temperature=0.3)

        if response.content:
            try:
                # Try to extract JSON from response
                content = response.content.strip()
                # Handle markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON: {response.content[:100]}")

        return {}

    @property
    def provider_name(self) -> str:
        return "mistral"

    @property
    def default_model(self) -> str:
        return self._model


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None and self._api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                logger.warning("OpenAI SDK not installed")
        return self._client

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        client = self._get_client()
        if not client:
            return LLMResponse(content="", model=self._model, provider=self.provider_name)

        start_time = time.time()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0

            return LLMResponse(
                content=content,
                model=self._model,
                provider=self.provider_name,
                tokens_used=tokens,
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return LLMResponse(content="", model=self._model, provider=self.provider_name)

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        client = self._get_client()
        if not client:
            return {}

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"OpenAI JSON generation failed: {e}")
            return {}

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return self._model


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None and self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                logger.warning("Anthropic SDK not installed")
        return self._client

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        client = self._get_client()
        if not client:
            return LLMResponse(content="", model=self._model, provider=self.provider_name)

        start_time = time.time()

        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system or "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )

            content = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            return LLMResponse(
                content=content,
                model=self._model,
                provider=self.provider_name,
                tokens_used=tokens,
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            return LLMResponse(content="", model=self._model, provider=self.provider_name)

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        json_prompt = f"{prompt}\n\nRespond only with valid JSON."
        system = (system or "") + "\nYou must respond with valid JSON only, no markdown."

        response = self.generate(json_prompt, system, temperature=0.3)

        if response.content:
            try:
                return json.loads(response.content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from Anthropic")

        return {}

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return self._model


class LLMProviderManager:
    """
    Manages multiple LLM providers with fallback support.
    """

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._primary_provider: Optional[str] = None
        self._fallback_order: List[str] = []
        self._cache = LLMCache()
        self._enable_cache = True

        # Auto-register available providers
        self._auto_register()

    def _auto_register(self) -> None:
        """Auto-register providers based on available API keys."""
        if os.getenv("MISTRAL_API_KEY"):
            self.register_provider("mistral", MistralProvider())
            if not self._primary_provider:
                self._primary_provider = "mistral"

        if os.getenv("OPENAI_API_KEY"):
            self.register_provider("openai", OpenAIProvider())
            if not self._primary_provider:
                self._primary_provider = "openai"

        if os.getenv("ANTHROPIC_API_KEY"):
            self.register_provider("anthropic", AnthropicProvider())
            if not self._primary_provider:
                self._primary_provider = "anthropic"

        # Set fallback order
        self._fallback_order = list(self._providers.keys())

    def register_provider(
        self,
        name: str,
        provider: BaseLLMProvider
    ) -> None:
        """Register an LLM provider."""
        self._providers[name] = provider
        logger.info(f"Registered LLM provider: {name}")

    def set_primary(self, name: str) -> None:
        """Set the primary provider."""
        if name in self._providers:
            self._primary_provider = name

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: Optional[str] = None,
        use_cache: bool = True
    ) -> LLMResponse:
        """
        Generate with automatic fallback.
        """
        target_provider = provider or self._primary_provider
        all_providers = [target_provider] + [
            p for p in self._fallback_order if p != target_provider
        ]

        # Check cache first
        if use_cache and self._enable_cache:
            cached = self._cache.get(
                prompt,
                self._providers[target_provider].default_model if target_provider else "",
                temperature,
                system
            )
            if cached:
                return cached

        # Try providers in order
        for prov_name in all_providers:
            if prov_name not in self._providers:
                continue

            provider_instance = self._providers[prov_name]
            response = provider_instance.generate(prompt, system, temperature, max_tokens)

            if response.content:
                # Cache successful response
                if use_cache and self._enable_cache:
                    self._cache.put(
                        prompt,
                        provider_instance.default_model,
                        temperature,
                        response,
                        system
                    )
                return response

            logger.warning(f"Provider {prov_name} failed, trying fallback")

        # All failed
        return LLMResponse(
            content="",
            model="unknown",
            provider="none"
        )

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON with fallback."""
        target_provider = provider or self._primary_provider

        if target_provider and target_provider in self._providers:
            result = self._providers[target_provider].generate_json(prompt, system)
            if result:
                return result

        # Try fallbacks
        for prov_name in self._fallback_order:
            if prov_name == target_provider or prov_name not in self._providers:
                continue

            result = self._providers[prov_name].generate_json(prompt, system)
            if result:
                return result

        return {}

    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self._providers.keys())

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()


# Singleton
_llm_manager: Optional[LLMProviderManager] = None


def get_llm_provider() -> LLMProviderManager:
    """Get or create LLM provider manager."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMProviderManager()
    return _llm_manager


def reset_llm_provider() -> None:
    """Reset LLM provider (for testing)."""
    global _llm_manager
    _llm_manager = None
