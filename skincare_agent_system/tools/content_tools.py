"""
Content Transformation Tools.
Each tool wraps a specific logic block and provides a standardized interface.
"""

from typing import Any, Dict, List

# Import existing logic blocks
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
from . import BaseTool, ToolResult


class BenefitsExtractorTool(BaseTool):
    """Extracts and enriches product benefits from raw data."""

    name = "benefits_extractor"
    description = "Extract benefits brightening hydration antioxidant"

    def run(self, product_data: Dict[str, Any]) -> ToolResult:
        try:
            benefits = extract_benefits(product_data)
            return ToolResult(success=True, data=benefits)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class UsageExtractorTool(BaseTool):
    """Extracts usage instructions from product data."""

    name = "usage_extractor"
    description = "Extract usage instructions how to use application"

    def run(self, product_data: Dict[str, Any]) -> ToolResult:
        try:
            usage = extract_usage_instructions(product_data)
            return ToolResult(success=True, data=usage)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FAQGeneratorTool(BaseTool):
    """Generates FAQ questions and answers from product data."""

    name = "faq_generator"
    description = "Generate FAQ questions answers categorized"

    def run(self, product_data: Dict[str, Any], min_questions: int = 10) -> ToolResult:
        try:
            qa_list = generate_questions_by_category(
                product_data, min_questions=min_questions
            )
            return ToolResult(success=True, data=qa_list)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ComparisonTool(BaseTool):
    """Compares two products and generates comparison insights."""

    name = "product_comparison"
    description = "Compare products ingredients price benefits winner recommendation"

    def run(self, product_a: Dict[str, Any], product_b: Dict[str, Any]) -> ToolResult:
        try:
            comparison = {
                "ingredients": compare_ingredients(product_a, product_b),
                "price": compare_prices(product_a, product_b),
                "benefits": compare_benefits(product_a, product_b),
                "winners": determine_winner(product_a, product_b),
                "recommendation": generate_recommendation(product_a, product_b),
            }
            return ToolResult(success=True, data=comparison)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# Factory function to create a pre-populated registry
def create_default_toolbox():
    """Creates a ToolRegistry with all default tools registered."""
    from . import ToolRegistry

    registry = ToolRegistry()
    registry.register(BenefitsExtractorTool())
    registry.register(UsageExtractorTool())
    registry.register(FAQGeneratorTool())
    registry.register(ComparisonTool())
    return registry
