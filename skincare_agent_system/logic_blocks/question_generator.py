"""
Question Generator Block - LLM-powered FAQ question generation.
Uses LLM when available, falls back to template-based generation otherwise.
"""

import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("QuestionGenerator")


def get_llm_client():
    """Get LLM client for content generation."""
    try:
        from ..infrastructure.llm_client import LLMClient
        client = LLMClient()
        # Check if actually usable
        if client:
            return client
    except Exception:
        pass
    return None


def generate_questions_by_category(
    product_data: Dict[str, Any], min_questions: int = 15
) -> List[Tuple[str, str, str]]:
    """
    Generate categorized questions and answers.
    Uses LLM if available, otherwise uses template-based generation.
    """
    llm = get_llm_client()
    
    if llm:
        for attempt in range(3):
            try:
                questions = _generate_questions_llm(llm, product_data, min_questions)
                if len(questions) >= min_questions:
                    logger.info(f"LLM generated {len(questions)} questions")
                    return questions
            except Exception as e:
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
    
    # Fallback to template-based generation
    logger.info("Using template-based question generation")
    return _generate_questions_template(product_data, min_questions)


def _generate_questions_llm(
    llm, product_data: Dict[str, Any], min_questions: int
) -> List[Tuple[str, str, str]]:
    """Use LLM to generate Q&As."""
    prompt = f"""
You are a skincare FAQ writer. Generate {min_questions} questions and answers.

Product: {product_data.get('name', 'Unknown')}
Ingredients: {', '.join(product_data.get('key_ingredients', []))}
Benefits: {', '.join(product_data.get('benefits', []))}
Skin Types: {', '.join(product_data.get('skin_types', []))}
Usage: {product_data.get('usage_instructions', 'N/A')}
Side Effects: {product_data.get('side_effects', 'None')}
Price: ₹{product_data.get('price', 'N/A')}

Generate {min_questions} Q&As across: Informational, Usage, Safety, Purchase, Comparison, Results

Return JSON array:
[{{"question": "...", "answer": "...", "category": "..."}}]
"""
    
    response = llm.generate_json(prompt)
    
    if isinstance(response, list):
        questions = []
        for item in response:
            if isinstance(item, dict):
                q = item.get("question", "")
                a = item.get("answer", "")
                c = item.get("category", "General")
                if q and a:
                    questions.append((q, a, c))
        return questions
    
    return []


def _generate_questions_template(
    product_data: Dict[str, Any], min_questions: int
) -> List[Tuple[str, str, str]]:
    """Template-based question generation (fallback)."""
    name = product_data.get("name", "this product")
    ingredients = ", ".join(product_data.get("key_ingredients", ["active ingredients"]))
    benefits = ", ".join(product_data.get("benefits", ["skincare benefits"]))
    skin_types = ", ".join(product_data.get("skin_types", ["all skin types"]))
    usage = product_data.get("usage_instructions", "Follow package directions")
    side_effects = product_data.get("side_effects", "No significant side effects")
    price = product_data.get("price", "N/A")
    
    questions = [
        # Informational
        (f"What is {name}?", f"{name} is a skincare product containing {ingredients}.", "Informational"),
        (f"What are the key ingredients in {name}?", f"The key ingredients are {ingredients}.", "Informational"),
        (f"What are the benefits of {name}?", f"{name} provides {benefits}.", "Informational"),
        
        # Usage
        (f"How do I use {name}?", usage, "Usage"),
        (f"When should I apply {name}?", f"Apply as part of your daily skincare routine. {usage}", "Usage"),
        (f"Can I use {name} with other products?", f"Yes, {name} can be layered with other products.", "Usage"),
        
        # Safety
        (f"Is {name} suitable for my skin type?", f"{name} is suitable for {skin_types}.", "Safety"),
        ("Are there any side effects?", side_effects, "Safety"),
        (f"Is {name} safe for sensitive skin?", f"Perform a patch test first. {side_effects}", "Safety"),
        
        # Purchase
        (f"How much does {name} cost?", f"{name} is priced at ₹{price}.", "Purchase"),
        (f"Where can I buy {name}?", f"Purchase from authorized retailers and online stores.", "Purchase"),
        
        # Results
        (f"How long until I see results?", "Most users notice improvements within 2-4 weeks.", "Results"),
        (f"Will {name} work for dark spots?", f"Yes, {name} helps with brightening and fading dark spots.", "Results"),
        
        # General
        ("Is this product cruelty-free?", "Yes, we are committed to cruelty-free practices.", "Ethics"),
        ("Is the packaging recyclable?", "Yes, our packaging is designed to be recyclable.", "Sustainability"),
        ("What is the shelf life?", "12 months after opening.", "Usage"),
        ("Can I use it during pregnancy?", "Consult your doctor before using during pregnancy.", "Safety"),
        ("Does it contain parabens?", "No, this product is paraben-free.", "Ingredients"),
        ("Is it vegan?", "Yes, this formulation is 100% vegan.", "Ethics"),
    ]
    
    return questions[:min_questions]
