"""
Integration tests for the full pipeline.
Run with: pytest tests/test_pipeline.py
"""
import pytest
import json
import os
from pathlib import Path
import sys

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skincare_agent_system"))

from skincare_agent_system.data.products import GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT
from skincare_agent_system.generate_content import (
    generate_faq_page,
    generate_product_page,
    generate_comparison_page
)


class TestPipeline:
    """Integration tests for the full content generation pipeline."""
    
    @pytest.fixture
    def output_dir(self, tmp_path):
        """Create temporary output directory."""
        return tmp_path / "output"
    
    def test_generate_faq_page(self, output_dir):
        """Test FAQ page generation."""
        output_path = str(output_dir / "faq.json")
        
        result = generate_faq_page(GLOWBOOST_PRODUCT, output_path)
        
        # Check structure
        assert "product" in result
        assert "total_questions" in result
        assert "faqs" in result
        
        # Check content
        assert result["product"] == "GlowBoost Vitamin C Serum"
        assert result["total_questions"] >= 15
        assert len(result["faqs"]) >= 15
        
        # Check file was created
        assert os.path.exists(output_path)
        
        # Validate JSON
        with open(output_path, 'r') as f:
            data = json.load(f)
            assert data == result
    
    def test_generate_product_page(self, output_dir):
        """Test product page generation."""
        output_path = str(output_dir / "product_page.json")
        
        result = generate_product_page(GLOWBOOST_PRODUCT, output_path)
        
        # Check structure
        assert "product_info" in result
        assert "benefits" in result
        assert "ingredients" in result
        assert "usage" in result
        assert "pricing" in result
        
        # Check content
        assert result["product_info"]["name"] == "GlowBoost Vitamin C Serum"
        assert result["pricing"]["price"] == 699
        
        # Check file was created
        assert os.path.exists(output_path)
    
    def test_generate_comparison_page(self, output_dir):
        """Test comparison page generation."""
        output_path = str(output_dir / "comparison_page.json")
        
        result = generate_comparison_page(
            GLOWBOOST_PRODUCT,
            RADIANCE_PLUS_PRODUCT,
            output_path
        )
        
        # Check structure
        assert "comparison_type" in result
        assert "primary_product" in result
        assert "comparison_with" in result
        assert "comparison_table" in result
        assert "winner_categories" in result
        
        # Check content
        assert result["primary_product"] == "GlowBoost Vitamin C Serum"
        assert result["comparison_with"] == "RadiancePlus Brightening Serum"
        
        # Check file was created
        assert os.path.exists(output_path)
    
    def test_full_pipeline(self, output_dir):
        """Test complete pipeline execution."""
        faq_path = str(output_dir / "faq.json")
        product_path = str(output_dir / "product_page.json")
        comparison_path = str(output_dir / "comparison_page.json")
        
        # Generate all outputs
        faq = generate_faq_page(GLOWBOOST_PRODUCT, faq_path)
        product = generate_product_page(GLOWBOOST_PRODUCT, product_path)
        comparison = generate_comparison_page(
            GLOWBOOST_PRODUCT,
            RADIANCE_PLUS_PRODUCT,
            comparison_path
        )
        
        # Verify all files exist
        assert os.path.exists(faq_path)
        assert os.path.exists(product_path)
        assert os.path.exists(comparison_path)
        
        # Verify all are valid JSON
        for path in [faq_path, product_path, comparison_path]:
            with open(path, 'r') as f:
                data = json.load(f)
                assert isinstance(data, dict)
    
    def test_faq_question_categories(self, output_dir):
        """Test that FAQ has multiple categories."""
        output_path = str(output_dir / "faq.json")
        result = generate_faq_page(GLOWBOOST_PRODUCT, output_path)
        
        categories = set()
        for faq in result["faqs"]:
            if "category" in faq:
                categories.add(faq["category"])
        
        # Should have multiple categories
        assert len(categories) >= 4
        assert "Informational" in categories
        assert "Usage" in categories
        assert "Safety" in categories


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
