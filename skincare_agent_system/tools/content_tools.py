"""
Content Transformation Tools.
Each tool wraps a specific logic block with:
1. Self-documenting names and clear arguments
2. Graceful error handling with descriptive messages
"""

from typing import Any, Dict

from ..logic_blocks.benefits_block import extract_benefits
from ..logic_blocks.comparison_block import (
    compare_benefits,
    compare_ingredients,
    compare_prices,
    determine_winner,
    generate_recommendation,
)
from ..logic_blocks.question_generator import generate_questions_by_category
from ..logic_blocks.usage_block import extract_usage_instructions
from . import BaseTool


class BenefitsExtractorTool(BaseTool):
    """
    Extract product benefits from raw data.

    Input: product_data (dict) with 'benefits' and 'key_ingredients' fields
    Output: List of benefit strings
    """

    name = "benefits_extractor"
    description = "Extract benefits brightening hydration antioxidant"

    def _execute(self, product_data: Dict[str, Any]) -> list:
        """Extract benefits from product data."""
        if not product_data:
            raise ValueError("product_data is required")
        if not isinstance(product_data, dict):
            raise TypeError("product_data must be a dictionary")

        return extract_benefits(product_data)


class UsageExtractorTool(BaseTool):
    """
    Extract usage instructions from product data.

    Input: product_data (dict) with 'usage_instructions' or 'how_to_use' field
    Output: Usage instruction string
    """

    name = "usage_extractor"
    description = "Extract usage instructions how to use application"

    def _execute(self, product_data: Dict[str, Any]) -> str:
        """Extract usage instructions."""
        if not product_data:
            raise ValueError("product_data is required")

        return extract_usage_instructions(product_data)


class FAQGeneratorTool(BaseTool):
    """
    Generate FAQ questions and answers from product data.

    Input:
        - product_data (dict): Product information
        - min_questions (int): Minimum questions to generate (default: 10)
    Output: List of (question, answer, category) tuples
    """

    name = "faq_generator"
    description = "Generate FAQ questions answers categorized"

    def _execute(
        self,
        product_data: Dict[str, Any],
        min_questions: int = 10
    ) -> list:
        """Generate FAQ questions."""
        if not product_data:
            raise ValueError("product_data is required")
        if min_questions < 1:
            raise ValueError("min_questions must be at least 1")

        return generate_questions_by_category(
            product_data, min_questions=min_questions
        )


class ComparisonTool(BaseTool):
    """
    Compare two products and generate insights.

    Input:
        - product_a (dict): Primary product data
        - product_b (dict): Comparison product data
    Output: Comparison dict with ingredients, price, benefits, winners
    """

    name = "product_comparison"
    description = "Compare products ingredients price benefits winner"

    def _execute(
        self,
        product_a: Dict[str, Any],
        product_b: Dict[str, Any]
    ) -> dict:
        """Compare two products."""
        if not product_a:
            raise ValueError("product_a is required")
        if not product_b:
            raise ValueError("product_b is required")

        return {
            "ingredients": compare_ingredients(product_a, product_b),
            "price": compare_prices(product_a, product_b),
            "benefits": compare_benefits(product_a, product_b),
            "winners": determine_winner(product_a, product_b),
            "recommendation": generate_recommendation(product_a, product_b),
        }


def create_default_toolbox():
    """Create a ToolRegistry with all default tools (no role restriction)."""
    from . import ToolRegistry

    registry = ToolRegistry()
    registry.register(BenefitsExtractorTool())
    registry.register(UsageExtractorTool())
    registry.register(FAQGeneratorTool())
    registry.register(ComparisonTool())
    return registry
