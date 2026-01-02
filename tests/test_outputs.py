import pytest

from skincare_agent_system.templates.faq_template import FAQTemplate
from skincare_agent_system.templates.product_page_template import ProductPageTemplate


def test_faq_template_output():
    template = FAQTemplate()
    # Now expects (question, answer, category) tuples
    data = {"product_name": "TestProduct", "qa_pairs": [("Q1", "A1", "Cat1"), ("Q2", "A2", "Cat2")]}
    output = template.render(data)
    assert output["product"] == "TestProduct"
    assert len(output["faqs"]) == 2
    assert output["faqs"][0]["question"] == "Q1"


def test_product_page_template_output():
    template = ProductPageTemplate()
    data = {
        "name": "TestProduct",
        "brand": "TestBrand",
        "benefits": ["B1"],
        "ingredients": ["I1"],
        "usage_instructions": "Use it",
        "price": 20.0,
    }
    output = template.render(data)
    assert output["product_info"]["name"] == "TestProduct"
    assert "B1" in output["benefits"]
