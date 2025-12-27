"""
Unit tests for logic blocks.
Run with: pytest tests/test_logic_blocks.py
"""

import pytest

from skincare_agent_system.logic_blocks.benefits_block import (
    categorize_benefits,
    extract_benefits,
    generate_benefits_copy,
)
from skincare_agent_system.logic_blocks.comparison_block import (
    compare_ingredients,
    compare_prices,
    determine_winner,
)
from skincare_agent_system.logic_blocks.question_generator import (
    generate_questions_by_category,
)
from skincare_agent_system.logic_blocks.usage_block import (
    extract_usage_instructions,
    format_usage_steps,
    generate_timing_recommendation,
)


class TestBenefitsBlock:
    """Test benefits extraction and formatting."""

    def test_extract_benefits_from_list(self):
        product = {"benefits": ["Brightening", "Hydration"]}
        result = extract_benefits(product)
        assert "Brightening" in result
        assert "Hydration" in result

    def test_extract_benefits_from_ingredients(self):
        product = {"key_ingredients": ["Vitamin C", "Hyaluronic Acid"], "benefits": []}
        result = extract_benefits(product)
        assert len(result) > 0
        assert any("brighten" in b.lower() for b in result)

    def test_generate_benefits_copy_single(self):
        benefits = ["Brightening"]
        result = generate_benefits_copy(benefits)
        assert "brightening" in result.lower()

    def test_generate_benefits_copy_multiple(self):
        benefits = ["Brightening", "Hydration", "Anti-aging"]
        result = generate_benefits_copy(benefits)
        assert "and" in result

    def test_categorize_benefits(self):
        benefits = ["Deep hydration", "Anti-aging", "Brightening"]
        result = categorize_benefits(benefits)
        assert "hydration" in result
        assert "anti_aging" in result
        assert "brightening" in result


class TestUsageBlock:
    """Test usage instruction extraction and formatting."""

    def test_extract_usage_direct(self):
        product = {"how_to_use": "Apply 2-3 drops morning and evening"}
        result = extract_usage_instructions(product)
        assert result == "Apply 2-3 drops morning and evening"

    def test_extract_usage_from_category(self):
        product = {"category": "serum"}
        result = extract_usage_instructions(product)
        assert "serum" in result.lower() or "drops" in result.lower()

    def test_format_usage_steps(self):
        usage = "Step 1. Cleanse. Step 2. Apply serum."
        result = format_usage_steps(usage)
        assert len(result) >= 1

    def test_timing_recommendation_retinol(self):
        product = {"key_ingredients": ["Retinol"]}
        result = generate_timing_recommendation(product)
        assert "evening" in result.lower()

    def test_timing_recommendation_vitamin_c(self):
        product = {"key_ingredients": ["Vitamin C"]}
        result = generate_timing_recommendation(product)
        assert "morning" in result.lower()


class TestComparisonBlock:
    """Test product comparison logic."""

    def test_compare_ingredients(self):
        product_a = {"key_ingredients": ["Vitamin C", "Hyaluronic Acid"]}
        product_b = {"key_ingredients": ["Vitamin C", "Vitamin E"]}

        result = compare_ingredients(product_a, product_b)

        assert "vitamin c" in result["common_ingredients"]
        assert "hyaluronic acid" in result["unique_to_a"]
        assert "vitamin e" in result["unique_to_b"]

    def test_compare_prices(self):
        product_a = {"price": 699, "name": "Product A"}
        product_b = {"price": 899, "name": "Product B"}

        result = compare_prices(product_a, product_b)

        assert result["difference"] == 200
        assert result["cheaper_product"] == "Product A"

    def test_determine_winner(self):
        product_a = {
            "name": "Product A",
            "price": 699,
            "key_ingredients": ["Vitamin C", "Hyaluronic Acid"],
            "benefits": ["Brightening"],
        }
        product_b = {
            "name": "Product B",
            "price": 899,
            "key_ingredients": ["Vitamin C"],
            "benefits": ["Brightening", "Anti-aging"],
        }

        result = determine_winner(product_a, product_b)

        assert result["best_value"] == "Product A"
        assert result["most_comprehensive"] == "Product A"
        assert result["most_benefits"] == "Product B"


class TestQuestionGenerator:
    """Test FAQ question generation."""

    def test_generate_minimum_questions(self):
        product = {
            "name": "Test Product",
            "key_ingredients": ["Vitamin C"],
            "benefits": ["Brightening"],
            "how_to_use": "Apply daily",
            "side_effects": "None",
            "price": 699,
            "skin_types": ["Oily"],
        }

        result = generate_questions_by_category(product, min_questions=15)

        assert len(result) >= 15

    def test_question_categories(self):
        product = {
            "name": "Test Product",
            "key_ingredients": ["Vitamin C"],
            "benefits": ["Brightening"],
            "how_to_use": "Apply daily",
            "side_effects": "None",
            "price": 699,
            "skin_types": ["Oily"],
        }

        result = generate_questions_by_category(product)
        categories = set(category for _, _, category in result)

        assert "Informational" in categories
        assert "Usage" in categories
        assert "Safety" in categories

    def test_question_structure(self):
        product = {
            "name": "Test Product",
            "key_ingredients": ["Vitamin C"],
            "benefits": ["Brightening"],
            "how_to_use": "Apply daily",
            "side_effects": "None",
            "price": 699,
        }

        result = generate_questions_by_category(product)

        for question, answer, category in result:
            assert isinstance(question, str)
            assert isinstance(answer, str)
            assert isinstance(category, str)
            assert len(question) > 0
            assert len(answer) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
