"""
LLM Abstraction Layer with Provider Pattern.
Supports graceful degradation to heuristics.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger("LLMClient")


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if LLM is available."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class MistralLLMProvider(LLMProvider):
    """Mistral API provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from mistralai.client import MistralClient
                self._client = MistralClient(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Mistral: {e}")

    @property
    def name(self) -> str:
        return "Mistral"

    def is_available(self) -> bool:
        return self._client is not None

    def generate(self, prompt: str, **kwargs) -> str:
        if not self.is_available():
            raise RuntimeError("Mistral client not initialized")

        response = self._client.chat(
            model=kwargs.get("model", "open-mistral-7b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7)
        )
        return response.choices[0].message.content


class HeuristicLLMProvider(LLMProvider):
    """Fallback heuristic provider (no API required)."""

    @property
    def name(self) -> str:
        return "Heuristic"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs) -> str:
        """Simple rule-based generation for offline mode."""
        prompt_lower = prompt.lower()
        if "benefits" in prompt_lower:
            return "Analyze product benefits from ingredient data"
        elif "question" in prompt_lower:
            return "Generate questions covering usage, safety, and efficacy"
        elif "compare" in prompt_lower:
            return "Compare products based on ingredients, price, and benefits"
        return "Process the data systematically"


class LLMFactory:
    """Factory for creating appropriate LLM provider."""

    @staticmethod
    def create(prefer_api: bool = True) -> LLMProvider:
        """Create LLM provider with graceful degradation."""
        if prefer_api:
            try:
                mistral = MistralLLMProvider()
                if mistral.is_available():
                    logger.info("✓ Using Mistral API for LLM operations")
                    return mistral
            except Exception as e:
                logger.warning(f"Mistral API unavailable: {e}")

        logger.info("✓ Using heuristic fallback (offline mode)")
        return HeuristicLLMProvider()


class LLMClient:
    """Unified LLM interface with automatic fallback."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or LLMFactory.create()
        self._print_status()

    def _print_status(self):
        if self.provider.is_available():
            print(f"✓ Using {self.provider.name} for LLM")

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text with automatic fallback."""
        try:
            return self.provider.generate(prompt, **kwargs)
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}, using heuristic")
            return HeuristicLLMProvider().generate(prompt, **kwargs)

    def generate_json(self, prompt: str, **kwargs) -> Any:
        """Generate JSON - parse text response."""
        import json

        text = self.generate(prompt, **kwargs)
        try:
            clean_text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception:
            return {}

    def is_api_available(self) -> bool:
        """Check if API is being used."""
        return isinstance(self.provider, MistralLLMProvider) and self.provider.is_available()
