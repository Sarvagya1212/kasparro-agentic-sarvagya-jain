"""
Base template protocol for content generation.
All templates produce JSON-serializable dictionaries.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class ContentTemplate(ABC):
    """
    Base template protocol. All templates produce JSON serializable dicts.
    This is NOT an LLM prompt - it's a structured data transformer.
    """

    @abstractmethod
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform input data into a structured JSON-serializable output.

        Args:
            data: Input data dictionary

        Returns:
            JSON-serializable dictionary
        """
        pass

    def validate_required_fields(self, data: Dict[str, Any], required_fields: list) -> None:
        """
        Validate that all required fields are present in data.

        Args:
            data: Input data
            required_fields: List of required field names

        Raises:
            ValueError: If any required field is missing
        """
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
