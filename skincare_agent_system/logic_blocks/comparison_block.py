"""
Comparison Block - Reusable logic for comparing products.
"""

from typing import Any, Dict, List


def compare_ingredients(
    product_a: Dict[str, Any], product_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare ingredients between two products.

    Args:
        product_a: First product data
        product_b: Second product data

    Returns:
        Comparison results
    """
    ingredients_a = set(ing.lower() for ing in product_a.get("key_ingredients", []))
    ingredients_b = set(ing.lower() for ing in product_b.get("key_ingredients", []))

    common = ingredients_a & ingredients_b
    unique_a = ingredients_a - ingredients_b
    unique_b = ingredients_b - ingredients_a

    return {
        "common_ingredients": list(common),
        "unique_to_a": list(unique_a),
        "unique_to_b": list(unique_b),
        "similarity_score": len(common) / max(len(ingredients_a | ingredients_b), 1),
    }


def compare_prices(
    product_a: Dict[str, Any], product_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare prices and value between two products.

    Args:
        product_a: First product data
        product_b: Second product data

    Returns:
        Price comparison results
    """
    price_a = product_a.get("price", 0)
    price_b = product_b.get("price", 0)

    difference = abs(price_a - price_b)
    percentage_diff = (
        (difference / max(price_a, price_b)) * 100 if max(price_a, price_b) > 0 else 0
    )

    cheaper = (
        product_a.get("name", "Product A")
        if price_a < price_b
        else product_b.get("name", "Product B")
    )

    return {
        "price_a": price_a,
        "price_b": price_b,
        "difference": difference,
        "percentage_difference": round(percentage_diff, 1),
        "cheaper_product": cheaper,
        "better_value": cheaper,  # Simplified - could factor in size/concentration
    }


def compare_benefits(
    product_a: Dict[str, Any], product_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare benefits between two products.

    Args:
        product_a: First product data
        product_b: Second product data

    Returns:
        Benefits comparison results
    """
    benefits_a = set(b.lower() for b in product_a.get("benefits", []))
    benefits_b = set(b.lower() for b in product_b.get("benefits", []))

    common = benefits_a & benefits_b
    unique_a = benefits_a - benefits_b
    unique_b = benefits_b - benefits_a

    return {
        "common_benefits": list(common),
        "unique_to_a": list(unique_a),
        "unique_to_b": list(unique_b),
    }


def determine_winner(
    product_a: Dict[str, Any], product_b: Dict[str, Any], criteria: List[str] = None
) -> Dict[str, str]:
    """
    Determine winner in various categories.

    Args:
        product_a: First product data
        product_b: Second product data
        criteria: List of criteria to evaluate

    Returns:
        Dictionary mapping criteria to winner names
    """
    if criteria is None:
        criteria = ["price", "ingredients", "benefits"]

    winners = {}

    name_a = product_a.get("name", "Product A")
    name_b = product_b.get("name", "Product B")

    # Price winner (cheaper)
    if "price" in criteria:
        price_a = product_a.get("price", float("inf"))
        price_b = product_b.get("price", float("inf"))
        winners["best_value"] = name_a if price_a < price_b else name_b

    # Ingredients winner (more ingredients)
    if "ingredients" in criteria:
        count_a = len(product_a.get("key_ingredients", []))
        count_b = len(product_b.get("key_ingredients", []))
        winners["most_comprehensive"] = name_a if count_a > count_b else name_b

    # Benefits winner (more benefits)
    if "benefits" in criteria:
        count_a = len(product_a.get("benefits", []))
        count_b = len(product_b.get("benefits", []))
        winners["most_benefits"] = name_a if count_a > count_b else name_b

    # Concentration winner (if applicable)
    if "concentration" in product_a and "concentration" in product_b:
        # Extract numeric concentration
        conc_a = extract_concentration_value(product_a.get("concentration", ""))
        conc_b = extract_concentration_value(product_b.get("concentration", ""))
        if conc_a and conc_b:
            winners["higher_concentration"] = name_a if conc_a > conc_b else name_b

    return winners


def extract_concentration_value(concentration_str: str) -> float:
    """
    Extract numeric concentration value from string.

    Args:
        concentration_str: Concentration string (e.g., "10%", "5% Niacinamide")

    Returns:
        Numeric concentration value
    """
    import re

    match = re.search(r"(\d+(?:\.\d+)?)\s*%", concentration_str)
    return float(match.group(1)) if match else 0.0


def generate_recommendation(
    product_a: Dict[str, Any], product_b: Dict[str, Any]
) -> str:
    """
    Generate recommendation using intelligence provider.
    Uses dynamic rule-based generation when LLM unavailable.
    """
    from ..infrastructure.providers import get_provider

    provider = get_provider()

    # Build prompt for LLM or context for rule-based
    prompt = f"""
Compare these skincare products and recommend:

Product A: {product_a.get('name', 'Product A')}
- Price: ₹{product_a.get('price', 0)}
- Ingredients: {', '.join(product_a.get('key_ingredients', []))}
- Skin Types: {', '.join(product_a.get('skin_types', []))}

Product B: {product_b.get('name', 'Product B')}  
- Price: ₹{product_b.get('price', 0)}
- Ingredients: {', '.join(product_b.get('key_ingredients', []))}
- Skin Types: {', '.join(product_b.get('skin_types', []))}

Provide a 2-3 sentence recommendation.
"""

    try:
        result = provider.generate(prompt, temperature=0.5)
        if result and len(result) > 20:
            return result.strip()
    except Exception:
        pass

    # Dynamic rule-based fallback (not static mock)
    return _generate_recommendation_rules(product_a, product_b)


def _generate_recommendation_rules(product_a: Dict, product_b: Dict) -> str:
    """Dynamic rule-based recommendation using actual product data and metrics."""
    name_a = product_a.get("name", "Product A")
    name_b = product_b.get("name", "Product B")
    price_a = product_a.get("price", 0)
    price_b = product_b.get("price", 0)
    types_a = set(product_a.get("skin_types", []))
    types_b = set(product_b.get("skin_types", []))
    ingredients_a = set(product_a.get("key_ingredients", []))
    ingredients_b = set(product_b.get("key_ingredients", []))

    # Calculate specific metrics
    price_diff = abs(price_a - price_b)
    price_savings = (
        round((price_diff / max(price_a, price_b)) * 100)
        if max(price_a, price_b) > 0
        else 0
    )

    ingredient_overlap = len(ingredients_a & ingredients_b)
    total_ingredients = len(ingredients_a | ingredients_b)
    overlap_pct = (
        round(100 * ingredient_overlap / total_ingredients)
        if total_ingredients > 0
        else 0
    )

    parts = []

    # Price-based recommendation with specifics
    if price_a and price_b:
        if price_a < price_b:
            parts.append(
                f"{name_a} offers {price_savings}% better value at ₹{price_a} vs ₹{price_b}"
            )
        else:
            parts.append(
                f"{name_b} is {price_savings}% more affordable at ₹{price_b} vs ₹{price_a}"
            )

    # Ingredient analysis
    if overlap_pct > 70:
        parts.append(f"Both products share {overlap_pct}% of active ingredients")
    elif overlap_pct < 30:
        parts.append(f"Products have distinct formulations ({overlap_pct}% overlap)")

    # Skin type recommendation
    if types_a and types_b:
        unique_a = types_a - types_b
        unique_b = types_b - types_a
        if unique_a:
            parts.append(f"{name_a} additionally suits {', '.join(unique_a)}")
        if unique_b:
            parts.append(f"{name_b} is better for {', '.join(unique_b)}")

    if not parts:
        parts.append(f"Both {name_a} and {name_b} are comparable options")

    return ". ".join(parts) + "."
