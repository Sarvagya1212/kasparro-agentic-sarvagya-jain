"""
Comparison Template - Structures product comparison into JSON format.
"""

from typing import Dict, Any
from .base_template import ContentTemplate


class ComparisonTemplate(ContentTemplate):
    """Template for product comparison page generation."""

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render comparison data into structured JSON format.

        Expected data format:
        {
            "primary": Dict (product A data),
            "other": Dict (product B data),
            "differences": List[Dict],
            "recommendation": str
        }

        Returns:
            JSON-serializable comparison structure
        """
        self.validate_required_fields(data, ["primary", "other"])

        primary = data["primary"]
        other = data["other"]

        # Build comparison table
        comparison_table = [
            {
                "attribute": "Product Name",
                "product_a": primary.get("name", ""),
                "product_b": other.get("name", ""),
            },
            {
                "attribute": "Price",
                "product_a": f"₹{primary.get('price', 0)}",
                "product_b": f"₹{other.get('price', 0)}",
            },
            {
                "attribute": "Key Ingredients",
                "product_a": ", ".join(primary.get("ingredients", [])),
                "product_b": ", ".join(other.get("ingredients", [])),
            },
            {
                "attribute": "Skin Types",
                "product_a": ", ".join(primary.get("skin_types", [])),
                "product_b": ", ".join(other.get("skin_types", [])),
            },
            {
                "attribute": "Benefits",
                "product_a": ", ".join(primary.get("benefits", [])),
                "product_b": ", ".join(other.get("benefits", [])),
            },
        ]

        return {
            "comparison_type": "side_by_side",
            "primary_product": primary.get("name", ""),
            "comparison_with": other.get("name", ""),
            "comparison_table": comparison_table,
            "differences": data.get("differences", []),
            "recommendation": data.get(
                "recommendation", "Both products have their merits"
            ),
            "winner_categories": data.get("winner_categories", {}),
        }
