"""Simple LLM abstraction with graceful degradation"""

import os
from typing import Optional


class LLMClient:
    """Unified LLM interface with fallback"""

    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.use_api = bool(self.api_key)
        self._client = None

        if self.use_api:
            try:
                from mistralai.client import MistralClient

                self._client = MistralClient(api_key=self.api_key)
                print("✓ Using Mistral API")
            except Exception as e:
                print(f"⚠ Mistral unavailable, using heuristics: {e}")
                self.use_api = False

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text with automatic fallback"""
        if self.use_api and self._client:
            try:
                response = self._client.chat(
                    model="open-mistral-7b",
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
            except Exception:
                pass  # Fall through to heuristic

        # Heuristic fallback
        return self._heuristic_response(prompt)

    def generate_json(self, prompt: str, **kwargs) -> Any:
        """Generate JSON - trying to parse text response"""
        import json

        text = self.generate(prompt, **kwargs)
        # Naive attempt to find JSON list/dict
        try:
            # removing markdown code blocks if any
            clean_text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except:
            # Logic blocks usually handle fallback if we return None or invalid
            # But here we might want to return a best guess or empty
            return {}

    def _heuristic_response(self, prompt: str) -> str:
        """Simple rule-based fallback"""
        if "benefits" in prompt.lower():
            return "Analyze product benefits from ingredient data"
        elif "question" in prompt.lower():
            return "Generate questions covering usage, safety, and efficacy"
        return "Process the data systematically"


# Global singleton
llm_client = LLMClient()
from typing import Any
