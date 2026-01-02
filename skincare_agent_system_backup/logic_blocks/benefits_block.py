"""
Benefits Block - Reusable logic for extracting and formatting product benefits.
"""

from typing import Any, Dict, List


def extract_benefits(product_data: Dict[str, Any]) -> List[str]:
    """
    Extract benefits from product data.

    Args:
        product_data: Product information dictionary

    Returns:
        List of benefit strings
    """
    benefits = []

    # Direct benefits field
    if "benefits" in product_data:
        if isinstance(product_data["benefits"], list):
            benefits.extend(product_data["benefits"])
        elif isinstance(product_data["benefits"], str):
            benefits.append(product_data["benefits"])

    # Infer benefits from ingredients
    ingredient_benefits = {
        "vitamin c": "Brightening and antioxidant protection",
        "hyaluronic acid": "Deep hydration and plumping",
        "niacinamide": "Pore refinement and oil control",
        "retinol": "Anti-aging and cell renewal",
        "salicylic acid": "Acne treatment and exfoliation",
        "ceramides": "Skin barrier repair",
    }

    ingredients = product_data.get("key_ingredients", [])
    for ingredient in ingredients:
        ingredient_lower = ingredient.lower()
        for key, benefit in ingredient_benefits.items():
            if key in ingredient_lower and benefit not in benefits:
                benefits.append(benefit)

    return benefits


def generate_benefits_copy(benefits: List[str]) -> str:
    """
    Generate marketing copy from benefits list.

    Args:
        benefits: List of benefit strings

    Returns:
        Formatted benefits copy
    """
    if not benefits:
        return "This product offers multiple skincare benefits."

    if len(benefits) == 1:
        return f"This product provides {benefits[0].lower()}."

    if len(benefits) == 2:
        return f"This product provides {benefits[0].lower()} and {benefits[1].lower()}."

    # Multiple benefits
    formatted = ", ".join(benefits[:-1]) + f", and {benefits[-1].lower()}"
    return f"This product provides {formatted}."


def categorize_benefits(benefits: List[str]) -> Dict[str, List[str]]:
    """
    Categorize benefits into groups.

    Args:
        benefits: List of benefit strings

    Returns:
        Dictionary mapping categories to benefits
    """
    categories = {
        "hydration": [],
        "anti_aging": [],
        "brightening": [],
        "treatment": [],
        "protection": [],
    }

    for benefit in benefits:
        benefit_lower = benefit.lower()

        if any(word in benefit_lower for word in ["hydrat", "moisture", "plump"]):
            categories["hydration"].append(benefit)
        elif any(word in benefit_lower for word in ["aging", "wrinkle", "fine line"]):
            categories["anti_aging"].append(benefit)
        elif any(
            word in benefit_lower for word in ["bright", "dark spot", "even tone"]
        ):
            categories["brightening"].append(benefit)
        elif any(word in benefit_lower for word in ["acne", "pore", "exfoliat"]):
            categories["treatment"].append(benefit)
        elif any(
            word in benefit_lower for word in ["protect", "antioxidant", "barrier"]
        ):
            categories["protection"].append(benefit)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}
