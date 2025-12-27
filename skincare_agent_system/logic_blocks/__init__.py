"""Logic blocks package - Reusable content transformation functions."""
from .benefits_block import extract_benefits, generate_benefits_copy
from .usage_block import extract_usage_instructions, format_usage_steps
from .comparison_block import compare_ingredients, compare_prices, determine_winner
from .question_generator import generate_questions_by_category

__all__ = [
    "extract_benefits",
    "generate_benefits_copy",
    "extract_usage_instructions",
    "format_usage_steps",
    "compare_ingredients",
    "compare_prices",
    "determine_winner",
    "generate_questions_by_category"
]
