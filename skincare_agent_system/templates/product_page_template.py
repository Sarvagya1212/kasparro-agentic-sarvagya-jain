"""
Product Page Template - Uses Jinja2 for structured JSON generation.
"""

import json
import os
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader

from .base_template import ContentTemplate


class ProductPageTemplate(ContentTemplate):
    """Template for product page generation using Jinja2."""

    def __init__(self):
        template_dir = os.path.dirname(os.path.abspath(__file__))
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template('product_page.j2')

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render product page data using Jinja2 template.

        Expected data format:
        {
            "name": str,
            "brand": str,
            "concentration": str,
            "benefits": List[str],
            "ingredients": List[str],
            "usage_instructions": str,
            "price": float,
            "currency": str,
            "skin_types": List[str],
            "concerns": List[str],
            "side_effects": str
        }
        """
        # Create product object for template
        product = {
            "name": data.get("name", ""),
            "brand": data.get("brand", ""),
            "concentration": data.get("concentration", ""),
            "benefits": data.get("benefits", []),
            "key_ingredients": data.get("ingredients", []),
            "price": data.get("price", 0),
            "currency": data.get("currency", "INR"),
            "size": data.get("size", ""),
            "skin_types": data.get("skin_types", []),
            "side_effects": data.get("side_effects", "")
        }

        rendered = self.template.render(
            product=product,
            usage_instructions=data.get("usage_instructions", ""),
            concerns=data.get("concerns", [])
        )
        
        return json.loads(rendered)
