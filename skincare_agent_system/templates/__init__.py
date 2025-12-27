"""Templates package for content generation."""

from .base_template import ContentTemplate
from .comparison_template import ComparisonTemplate
from .faq_template import FAQTemplate
from .product_page_template import ProductPageTemplate

__all__ = [
    "ContentTemplate",
    "FAQTemplate",
    "ProductPageTemplate",
    "ComparisonTemplate",
]
