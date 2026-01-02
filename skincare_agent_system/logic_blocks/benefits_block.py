"""
Benefits Block - LLM-powered content generation for product benefits.
Uses LLM for intelligent benefit extraction and copy generation.
Falls back to heuristics when LLM unavailable.
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger("BenefitsBlock")


def get_llm_client():
    """Get LLM client for content generation."""
    try:
        from ..infrastructure.llm_client import LLMClient
        return LLMClient()
    except Exception:
        return None


def extract_benefits(product_data: Dict[str, Any]) -> List[str]:
    """
    Extract benefits from product data using LLM.
    
    Args:
        product_data: Product information dictionary
    
    Returns:
        List of benefit strings
    """
    llm = get_llm_client()
    
    # Try LLM-based extraction first
    if llm:
        try:
            benefits = _extract_benefits_llm(llm, product_data)
            if benefits:
                logger.info(f"LLM extracted {len(benefits)} benefits")
                return benefits
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, using heuristics")
    
    # Fallback to heuristic extraction
    return _extract_benefits_heuristic(product_data)


def _extract_benefits_llm(llm, product_data: Dict[str, Any]) -> List[str]:
    """Use LLM to intelligently extract and expand benefits."""
    prompt = f"""
You are a skincare product analyst. Given this product data, extract and expand the key benefits.

Product Data:
- Name: {product_data.get('name', 'Unknown')}
- Key Ingredients: {', '.join(product_data.get('key_ingredients', []))}
- Listed Benefits: {', '.join(product_data.get('benefits', []))}
- Skin Types: {', '.join(product_data.get('skin_types', []))}

Instructions:
1. Keep the original listed benefits
2. Add benefits inferred from the key ingredients (e.g., Vitamin C → Brightening, Antioxidant)
3. Format each benefit as a clear, consumer-friendly statement
4. Return 5-8 unique benefits

Return ONLY a JSON array of benefit strings, no explanation:
["benefit 1", "benefit 2", ...]
"""
    
    response = llm.generate(prompt, temperature=0.3)
    
    # Parse JSON from response
    try:
        # Try to find JSON array in response
        import re
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            benefits = json.loads(match.group())
            if isinstance(benefits, list):
                return [str(b) for b in benefits if b]
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}")
    
    return []


def _extract_benefits_heuristic(product_data: Dict[str, Any]) -> List[str]:
    """Fallback heuristic extraction when LLM unavailable."""
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
    Generate marketing copy from benefits list using LLM.
    
    Args:
        benefits: List of benefit strings
    
    Returns:
        Formatted benefits copy
    """
    if not benefits:
        return "This product offers multiple skincare benefits."
    
    llm = get_llm_client()
    
    if llm:
        try:
            prompt = f"""
Write a compelling 1-2 sentence marketing description for a skincare product with these benefits:
{', '.join(benefits)}

Return ONLY the marketing copy, no quotes or explanation.
"""
            response = llm.generate(prompt, temperature=0.5)
            if response and len(response) > 10:
                return response.strip().strip('"')
        except Exception as e:
            logger.warning(f"LLM copy generation failed: {e}")
    
    # Fallback
    if len(benefits) == 1:
        return f"This product provides {benefits[0].lower()}."
    
    formatted = ", ".join(benefits[:-1]) + f", and {benefits[-1].lower()}"
    return f"This product provides {formatted}."


def categorize_benefits(benefits: List[str]) -> Dict[str, List[str]]:
    """
    Categorize benefits into groups using LLM.
    
    Args:
        benefits: List of benefit strings
    
    Returns:
        Dictionary mapping categories to benefits
    """
    if not benefits:
        return {}
    
    llm = get_llm_client()
    
    if llm:
        try:
            prompt = f"""
Categorize these skincare benefits into groups:
Benefits: {json.dumps(benefits)}

Categories to use: hydration, anti_aging, brightening, treatment, protection

Return ONLY a JSON object mapping categories to lists of benefits:
{{"hydration": [...], "brightening": [...], ...}}
Only include categories that have benefits. If a benefit doesn't fit, skip it.
"""
            response = llm.generate(prompt, temperature=0.2)
            
            import re
            match = re.search(r'\{.*?\}', response, re.DOTALL)
            if match:
                categories = json.loads(match.group())
                if isinstance(categories, dict):
                    return {k: v for k, v in categories.items() if v}
        except Exception as e:
            logger.warning(f"LLM categorization failed: {e}")
    
    # Fallback to heuristic categorization
    return _categorize_benefits_heuristic(benefits)


def _categorize_benefits_heuristic(benefits: List[str]) -> Dict[str, List[str]]:
    """Fallback heuristic categorization."""
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
        elif any(word in benefit_lower for word in ["bright", "dark spot", "even tone", "fade"]):
            categories["brightening"].append(benefit)
        elif any(word in benefit_lower for word in ["acne", "pore", "exfoliat"]):
            categories["treatment"].append(benefit)
        elif any(word in benefit_lower for word in ["protect", "antioxidant", "barrier"]):
            categories["protection"].append(benefit)

    return {k: v for k, v in categories.items() if v}
