"""
FAQ Template - Uses Jinja2 for structured JSON generation.
"""

import os
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader

from .base_template import ContentTemplate


class FAQTemplate(ContentTemplate):
    """Template for FAQ page generation using Jinja2."""

    def __init__(self):
        template_dir = os.path.dirname(os.path.abspath(__file__))
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template("faq.j2")

    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render FAQ data into structured JSON format using Jinja2.

        Expected data format:
        {
            "product_name": str,
            "qa_pairs": List[tuple[str, str, str]],
            # [(question, answer, category), ...]
        }

        Returns:
            JSON-serializable FAQ structure
        """
        self.validate_required_fields(data, ["product_name", "qa_pairs"])

        # Build FAQ list with categories
        faqs = []
        for question, answer, category in data["qa_pairs"]:
            faqs.append({"question": question, "answer": answer, "category": category})

        # Render using Jinja2
        import json

        rendered = self.template.render(
            product=data["product_name"],
            faqs=faqs,
            generated_at=data.get("timestamp", ""),
        )

        return json.loads(rendered)
