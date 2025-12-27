"""
Unit tests for templates.
Run with: pytest tests/test_templates.py
"""

import pytest
from skincare_agent_system.templates.faq_template import FAQTemplate
from skincare_agent_system.templates.product_page_template import ProductPageTemplate
from skincare_agent_system.templates.comparison_template import ComparisonTemplate


class TestFAQTemplate:
    """Test FAQ template rendering."""

    def test_render_basic(self):
        template = FAQTemplate()
        data = {
            "product_name": "Test Product",
            "qa_pairs": [("Question 1?", "Answer 1"), ("Question 2?", "Answer 2")],
        }

        result = template.render(data)

        assert result["product"] == "Test Product"
        assert result["total_questions"] == 2
        assert len(result["faqs"]) == 2

    def test_render_with_categories(self):
        template = FAQTemplate()
        data = {
            "product_name": "Test Product",
            "qa_pairs": [("Q1?", "A1"), ("Q2?", "A2")],
            "categories": {"Usage": [0], "Safety": [1]},
        }

        result = template.render(data)

        assert result["faqs"][0]["category"] == "Usage"
        assert result["faqs"][1]["category"] == "Safety"

    def test_missing_required_fields(self):
        template = FAQTemplate()
        data = {"product_name": "Test"}  # Missing qa_pairs

        with pytest.raises(ValueError):
            template.render(data)


class TestProductPageTemplate:
    """Test product page template rendering."""

    def test_render_complete(self):
        template = ProductPageTemplate()
        data = {
            "name": "Test Serum",
            "brand": "TestBrand",
            "benefits": ["Brightening", "Hydration"],
            "ingredients": ["Vitamin C", "Hyaluronic Acid"],
            "usage_instructions": "Apply daily",
            "price": 699,
            "skin_types": ["Oily", "Combination"],
        }

        result = template.render(data)

        assert result["product_info"]["name"] == "Test Serum"
        assert len(result["benefits"]) == 2
        assert result["ingredients"]["count"] == 2
        assert result["pricing"]["price"] == 699

    def test_render_with_defaults(self):
        template = ProductPageTemplate()
        data = {
            "name": "Test Serum",
            "benefits": ["Brightening"],
            "ingredients": ["Vitamin C"],
            "usage_instructions": "Apply daily",
            "price": 699,
        }

        result = template.render(data)

        assert result["product_info"]["brand"] == ""
        assert result["usage"]["side_effects"] == "None reported"

    def test_missing_required_fields(self):
        template = ProductPageTemplate()
        data = {"name": "Test"}  # Missing required fields

        with pytest.raises(ValueError):
            template.render(data)


class TestComparisonTemplate:
    """Test comparison template rendering."""

    def test_render_basic(self):
        template = ComparisonTemplate()
        data = {
            "primary": {
                "name": "Product A",
                "price": 699,
                "ingredients": ["Vitamin C"],
                "skin_types": ["Oily"],
                "benefits": ["Brightening"],
            },
            "other": {
                "name": "Product B",
                "price": 899,
                "ingredients": ["Vitamin E"],
                "skin_types": ["Dry"],
                "benefits": ["Anti-aging"],
            },
        }

        result = template.render(data)

        assert result["comparison_type"] == "side_by_side"
        assert result["primary_product"] == "Product A"
        assert result["comparison_with"] == "Product B"
        assert len(result["comparison_table"]) == 5

    def test_comparison_table_structure(self):
        template = ComparisonTemplate()
        data = {
            "primary": {
                "name": "Product A",
                "price": 699,
                "ingredients": ["Vitamin C"],
                "skin_types": ["Oily"],
                "benefits": ["Brightening"],
            },
            "other": {
                "name": "Product B",
                "price": 899,
                "ingredients": ["Vitamin E"],
                "skin_types": ["Dry"],
                "benefits": ["Anti-aging"],
            },
        }

        result = template.render(data)

        for row in result["comparison_table"]:
            assert "attribute" in row
            assert "product_a" in row
            assert "product_b" in row

    def test_missing_required_fields(self):
        template = ComparisonTemplate()
        data = {"primary": {}}  # Missing 'other'

        with pytest.raises(ValueError):
            template.render(data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
