"""
Comparison Template - Uses Jinja2 for structured JSON generation.
"""

import json
import os
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader

from .base_template import ContentTemplate


class ComparisonTemplate(ContentTemplate):
    """Template for comparison page generation using Jinja2."""

    def __init__(self):
        template_dir = os.path.dirname(os.path.abspath(__file__))
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template('comparison.j2')

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render comparison data using Jinja2 template with specific metrics.
        """
        primary = data.get("primary", {})
        other = data.get("other", {})
        
        # Calculate specific metrics
        price_a = primary.get("price", 0)
        price_b = other.get("price", 0)
        price_diff = abs(price_a - price_b)
        better_value = primary.get("name", "") if price_a < price_b else other.get("name", "")
        
        # Calculate ingredient overlap
        ingredients_a = set(primary.get("ingredients", []))
        ingredients_b = set(other.get("ingredients", []))
        overlap = len(ingredients_a & ingredients_b)
        total = len(ingredients_a | ingredients_b)
        ingredient_overlap = round(100 * overlap / total) if total > 0 else 0

        rendered = self.template.render(
            primary=primary,
            other=other,
            price_diff=price_diff,
            better_value=better_value,
            ingredient_overlap=ingredient_overlap,
            differences=data.get("differences", []),
            recommendation=data.get("recommendation", ""),
            winner_categories=data.get("winner_categories", {})
        )
        
        return json.loads(rendered)
