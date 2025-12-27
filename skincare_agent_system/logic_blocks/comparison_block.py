"""
Comparison Block - Reusable logic for comparing products.
"""
from typing import Dict, Any, List, Tuple


def compare_ingredients(product_a: Dict[str, Any], product_b: Dict[str, Any]) -> Dict[str, Any]:
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
        "similarity_score": len(common) / max(len(ingredients_a | ingredients_b), 1)
    }


def compare_prices(product_a: Dict[str, Any], product_b: Dict[str, Any]) -> Dict[str, Any]:
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
    percentage_diff = (difference / max(price_a, price_b)) * 100 if max(price_a, price_b) > 0 else 0
    
    cheaper = product_a.get("name", "Product A") if price_a < price_b else product_b.get("name", "Product B")
    
    return {
        "price_a": price_a,
        "price_b": price_b,
        "difference": difference,
        "percentage_difference": round(percentage_diff, 1),
        "cheaper_product": cheaper,
        "better_value": cheaper  # Simplified - could factor in size/concentration
    }


def compare_benefits(product_a: Dict[str, Any], product_b: Dict[str, Any]) -> Dict[str, Any]:
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
        "unique_to_b": list(unique_b)
    }


def determine_winner(product_a: Dict[str, Any], product_b: Dict[str, Any], 
                    criteria: List[str] = None) -> Dict[str, str]:
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
        price_a = product_a.get("price", float('inf'))
        price_b = product_b.get("price", float('inf'))
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
    match = re.search(r'(\d+(?:\.\d+)?)\s*%', concentration_str)
    return float(match.group(1)) if match else 0.0


def generate_recommendation(product_a: Dict[str, Any], product_b: Dict[str, Any]) -> str:
    """
    Generate overall recommendation based on comparison.
    
    Args:
        product_a: First product data
        product_b: Second product data
        
    Returns:
        Recommendation text
    """
    name_a = product_a.get("name", "Product A")
    name_b = product_b.get("name", "Product B")
    
    price_comp = compare_prices(product_a, product_b)
    
    if price_comp["cheaper_product"] == name_a:
        return f"For budget-conscious buyers, {name_a} offers excellent value. However, {name_b} may provide additional benefits worth the premium."
    else:
        return f"{name_a} is the premium option with comprehensive benefits, while {name_b} offers great value for those on a budget."
