"""Templates package for content generation."""

from .base_template import ContentTemplate
from .faq_template import FAQTemplate
from .product_page_template import ProductPageTemplate
from .comparison_template import ComparisonTemplate

__all__ = ["ContentTemplate", "FAQTemplate", "ProductPageTemplate", "ComparisonTemplate"]
