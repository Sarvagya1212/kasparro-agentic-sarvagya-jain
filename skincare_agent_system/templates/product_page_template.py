"""
Product Page Template - Structures product information into JSON format.
"""
from typing import Dict, Any
from .base_template import ContentTemplate


class ProductPageTemplate(ContentTemplate):
    """Template for product page generation."""
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render product data into structured JSON format.
        
        Expected data format:
        {
            "name": str,
            "brand": str,
            "benefits": List[str],
            "ingredients": List[str],
            "usage_instructions": str,
            "price": float,
            "skin_types": List[str],
            "concerns": List[str],
            "side_effects": Optional[str],
            "concentration": Optional[str]
        }
        
        Returns:
            JSON-serializable product page structure
        """
        required = ["name", "benefits", "ingredients", "usage_instructions", "price"]
        self.validate_required_fields(data, required)
        
        return {
            "product_info": {
                "name": data["name"],
                "brand": data.get("brand", ""),
                "concentration": data.get("concentration", "")
            },
            "benefits": data["benefits"],
            "ingredients": {
                "key_ingredients": data["ingredients"],
                "count": len(data["ingredients"])
            },
            "usage": {
                "instructions": data["usage_instructions"],
                "side_effects": data.get("side_effects", "None reported")
            },
            "suitability": {
                "skin_types": data.get("skin_types", []),
                "addresses_concerns": data.get("concerns", [])
            },
            "pricing": {
                "price": data["price"],
                "currency": data.get("currency", "INR"),
                "size": data.get("size", "")
            }
        }
