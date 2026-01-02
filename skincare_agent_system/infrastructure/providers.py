"""
Intelligence Provider Abstraction.
Uses only MistralProvider for LLM-based generation.
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


logger = logging.getLogger("Providers")


# ============================================================================
# Base Interface
# ============================================================================


class IIntelligenceProvider(ABC):
    """Abstract base for intelligence providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

    def generate_json(self, prompt: str, **kwargs) -> Any:
        """Default JSON generation via generate()."""
        response = self.generate(prompt, **kwargs)
        return json.loads(response)

    def generate_faq(self, product_data: Dict) -> List[Tuple[str, str, str]]:
        """Default FAQ generation - override if needed."""
        prompt = f"Generate 20 FAQs for product: {product_data.get('name', '')}"
        response = self.generate(prompt)
        # Parse response into tuples
        return []


# ============================================================================
# Mistral Provider
# ============================================================================


class MistralProvider(IIntelligenceProvider):
    """
    LLM integration via Mistral AI.
    Requires MISTRAL_API_KEY environment variable.
    """

    def __init__(self, max_retries: int = 3):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.max_retries = max_retries
        self._client = None

    @property
    def name(self) -> str:
        return "Mistral"

    def is_available(self) -> bool:
        """Check if Mistral API is configured."""
        if not self.api_key:
            logger.warning("MISTRAL_API_KEY not set")
            return False
        return True

    def _get_client(self):
        """Lazy load Mistral client."""
        if self._client is None:
            try:
                from mistralai.client import MistralClient

                self._client = MistralClient(api_key=self.api_key)
            except ImportError:
                logger.error("mistralai package not installed")
                raise ImportError("Install: pip install mistralai")
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Mistral AI with retries."""
        if not self.is_available():
            raise ValueError("Mistral provider not available - missing API key")

        temperature = kwargs.get("temperature", 0.7)
        model = kwargs.get("model", "mistral-small-latest")

        client = self._get_client()

        for attempt in range(self.max_retries):
            try:
                response = client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )

                if response and response.choices:
                    return response.choices[0].message.content

                raise ValueError("Empty response from Mistral")

            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Mistral API failed after {self.max_retries} retries")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2**attempt)  # Exponential backoff

        raise RuntimeError("Max retries exceeded")

    def generate_faq(self, product_data: Dict) -> List[Tuple[str, str, str]]:
        """Generate FAQs using Mistral."""
        name = product_data.get("name", "Product")
        ingredients = product_data.get("key_ingredients", [])
        skin_types = product_data.get("skin_types", [])

        prompt = f"""Generate exactly 20 FAQ questions and answers for this product.
Product: {name}
Ingredients: {', '.join(ingredients)}
Skin Types: {', '.join(skin_types)}

For each FAQ, provide:
1. Question (specific to the product)
2. Answer (informative, 1-2 sentences)
3. Category (one of: Informational, Usage, Safety, Purchase, Results)

Return ONLY valid JSON (no markdown):
[
  {{"question": "...", "answer": "...", "category": "Informational"}},
  ...
]"""

        try:
            response = self.generate(prompt, temperature=0.5)
            # Clean markdown if present
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]

            faqs = json.loads(cleaned.strip())

            result = []
            for faq in faqs[:20]:  # Ensure max 20
                result.append(
                    (
                        faq.get("question", ""),
                        faq.get("answer", ""),
                        faq.get("category", "General"),
                    )
                )

            return result

        except Exception as e:
            logger.error(f"FAQ generation failed: {e}")
            raise


# ============================================================================
# Provider Factory
# ============================================================================


def get_provider() -> IIntelligenceProvider:
    """Get the Mistral provider instance."""
    return MistralProvider()
