"""
Content Generation System - Orchestrator for the multi-agent content generation system.
This module provides a high-level interface to the content generation pipeline.
"""

from typing import Dict, Any
from pathlib import Path
import json


class ContentGenerationSystem:
    """
    High-level orchestrator for content generation.
    Provides a simple interface to generate all content types.
    """

    def __init__(self):
        """Initialize the content generation system."""
        self.output_dir = Path(__file__).parent.parent / "output"
        self.output_dir.mkdir(exist_ok=True)

    def generate_all_content(self, product_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate all content types for a product.

        Args:
            product_data: Product information dictionary

        Returns:
            Dictionary mapping content type to output file path
        """
        from generate_content import (
            generate_faq_page,
            generate_product_page,
            generate_comparison_page,
        )
        from data.products import RADIANCE_PLUS_PRODUCT

        outputs = {}

        # Generate FAQ
        faq_path = str(self.output_dir / "faq.json")
        generate_faq_page(product_data, faq_path)
        outputs["faq"] = faq_path

        # Generate Product Page
        product_path = str(self.output_dir / "product_page.json")
        generate_product_page(product_data, product_path)
        outputs["product"] = product_path

        # Generate Comparison
        comparison_path = str(self.output_dir / "comparison_page.json")
        generate_comparison_page(product_data, RADIANCE_PLUS_PRODUCT, comparison_path)
        outputs["comparison"] = comparison_path

        return outputs

    def generate_faq(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate FAQ content only."""
        from generate_content import generate_faq_page

        faq_path = str(self.output_dir / "faq.json")
        return generate_faq_page(product_data, faq_path)

    def generate_product_page(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate product page content only."""
        from generate_content import generate_product_page

        product_path = str(self.output_dir / "product_page.json")
        return generate_product_page(product_data, product_path)

    def generate_comparison(
        self, product_a: Dict[str, Any], product_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comparison content only."""
        from generate_content import generate_comparison_page

        comparison_path = str(self.output_dir / "comparison_page.json")
        return generate_comparison_page(product_a, product_b, comparison_path)

    def get_output_files(self) -> Dict[str, Path]:
        """Get paths to all generated output files."""
        return {
            "faq": self.output_dir / "faq.json",
            "product": self.output_dir / "product_page.json",
            "comparison": self.output_dir / "comparison_page.json",
        }

    def validate_outputs(self) -> bool:
        """
        Validate that all output files exist and are valid JSON.

        Returns:
            True if all outputs are valid, False otherwise
        """
        files = self.get_output_files()

        for name, filepath in files.items():
            if not filepath.exists():
                print(f"✗ Missing: {name}")
                return False

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    json.load(f)
                print(f"✓ Valid: {name}")
            except json.JSONDecodeError:
                print(f"✗ Invalid JSON: {name}")
                return False

        return True


def main():
    """Example usage of ContentGenerationSystem."""
    from data.products import GLOWBOOST_PRODUCT

    system = ContentGenerationSystem()

    print("\n" + "=" * 60)
    print("Content Generation System - Example Usage")
    print("=" * 60)

    # Generate all content
    outputs = system.generate_all_content(GLOWBOOST_PRODUCT)

    print("\n✓ Generated files:")
    for content_type, filepath in outputs.items():
        print(f"  - {content_type}: {filepath}")

    # Validate outputs
    print("\n" + "=" * 60)
    print("Validating Outputs")
    print("=" * 60)

    if system.validate_outputs():
        print("\n✅ All outputs are valid!")
    else:
        print("\n❌ Some outputs are invalid")


if __name__ == "__main__":
    main()
