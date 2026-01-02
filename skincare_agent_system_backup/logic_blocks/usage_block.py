"""
Usage Block - Reusable logic for extracting and formatting usage instructions.
"""

from typing import Any, Dict, List


def extract_usage_instructions(product_data: Dict[str, Any]) -> str:
    """
    Extract usage instructions from product data.

    Args:
        product_data: Product information dictionary

    Returns:
        Usage instructions string
    """
    # Direct usage field
    if "how_to_use" in product_data:
        return product_data["how_to_use"]

    if "usage" in product_data:
        return product_data["usage"]

    # Infer from category
    category = product_data.get("category", "").lower()

    usage_templates = {
        "serum": "Apply 2-3 drops to clean skin before moisturizer.",
        "moisturizer": "Apply to clean skin morning and evening.",
        "cleanser": "Massage onto damp skin, then rinse thoroughly.",
        "toner": "Apply to clean skin with a cotton pad or hands.",
        "mask": "Apply to clean skin, leave for 10-15 minutes, then rinse.",
        "sunscreen": "Apply generously 15 minutes before sun exposure.",
    }

    for key, template in usage_templates.items():
        if key in category:
            return template

    return "Follow product instructions for best results."


def format_usage_steps(usage_text: str) -> List[str]:
    """
    Format usage instructions into step-by-step list.

    Args:
        usage_text: Raw usage instructions

    Returns:
        List of usage steps
    """
    # Split by common delimiters
    steps = []

    # Try splitting by periods first
    if ". " in usage_text:
        potential_steps = usage_text.split(". ")
        steps = [
            step.strip() + "." if not step.endswith(".") else step.strip()
            for step in potential_steps
            if step.strip()
        ]
    else:
        steps = [usage_text]

    return steps


def generate_timing_recommendation(product_data: Dict[str, Any]) -> str:
    """
    Generate timing recommendation (AM/PM) based on product type.

    Args:
        product_data: Product information dictionary

    Returns:
        Timing recommendation string
    """
    category = product_data.get("category", "").lower()
    ingredients = [ing.lower() for ing in product_data.get("key_ingredients", [])]

    # Retinol/retinoids - PM only
    if any("retinol" in ing or "retinoid" in ing for ing in ingredients):
        return "Evening only (photosensitive)"

    # Vitamin C - typically AM
    if any("vitamin c" in ing for ing in ingredients):
        return "Morning (for antioxidant protection)"

    # Sunscreen - AM only
    if "sunscreen" in category or "spf" in category:
        return "Morning only"

    # AHAs/BHAs - typically PM
    if any(
        acid in " ".join(ingredients) for acid in ["salicylic", "glycolic", "lactic"]
    ):
        return "Evening preferred"

    # Default
    return "Morning and evening"


def extract_precautions(product_data: Dict[str, Any]) -> List[str]:
    """
    Extract or generate precautions based on product data.

    Args:
        product_data: Product information dictionary

    Returns:
        List of precautions
    """
    precautions = []

    # Direct side effects field
    if "side_effects" in product_data:
        side_effects = product_data["side_effects"]
        if side_effects and side_effects.lower() != "none":
            precautions.append(side_effects)

    # Ingredient-based precautions
    ingredients = [ing.lower() for ing in product_data.get("key_ingredients", [])]

    if any("retinol" in ing for ing in ingredients):
        precautions.append("May cause initial dryness or peeling")
        precautions.append("Use sunscreen during the day")

    if any("acid" in ing for ing in ingredients):
        precautions.append("Patch test recommended")
        precautions.append("May increase sun sensitivity")

    if any("vitamin c" in ing for ing in ingredients):
        precautions.append("Store in a cool, dark place to prevent oxidation")

    return precautions if precautions else ["Suitable for most skin types"]
