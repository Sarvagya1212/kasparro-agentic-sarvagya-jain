"""
Question Generator Block - LLM-powered FAQ question generation.
Uses LLM for intelligent question/answer generation.
Falls back to template-based generation when LLM unavailable.
"""

import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("QuestionGenerator")


def get_llm_client():
    """Get LLM client for content generation."""
    try:
        from ..infrastructure.llm_client import LLMClient
        return LLMClient()
    except Exception:
        return None


def generate_questions_by_category(
    product_data: Dict[str, Any], min_questions: int = 15
) -> List[Tuple[str, str, str]]:
    """
    Generate categorized questions and answers using LLM.

    Args:
        product_data: Product information dictionary
        min_questions: Minimum number of questions to generate

    Returns:
        List of tuples: (question, answer, category)
    """
    llm = get_llm_client()
    
    # Try LLM-based generation first
    if llm:
        try:
            questions = _generate_questions_llm(llm, product_data, min_questions)
            if len(questions) >= min_questions:
                logger.info(f"LLM generated {len(questions)} questions")
                return questions
        except Exception as e:
            logger.warning(f"LLM question generation failed: {e}, using fallback")
    
    # Fallback to template-based generation
    return _generate_questions_heuristic(product_data, min_questions)


def _generate_questions_llm(
    llm, product_data: Dict[str, Any], min_questions: int
) -> List[Tuple[str, str, str]]:
    """Use LLM to generate intelligent Q&As."""
    
    prompt = f"""
You are a skincare FAQ content writer. Generate {min_questions} customer questions and answers for this product.

Product Information:
- Name: {product_data.get('name', 'Unknown')}
- Brand: {product_data.get('brand', 'Unknown')}
- Concentration: {product_data.get('concentration', 'N/A')}
- Key Ingredients: {', '.join(product_data.get('key_ingredients', []))}
- Benefits: {', '.join(product_data.get('benefits', []))}
- Skin Types: {', '.join(product_data.get('skin_types', []))}
- How to Use: {product_data.get('usage_instructions', 'N/A')}
- Side Effects: {product_data.get('side_effects', 'None reported')}
- Price: ₹{product_data.get('price', 'N/A')}

Generate questions across these categories (at least 2 per category):
1. Informational - About the product itself
2. Usage - How to use, when, how often
3. Safety - Side effects, skin compatibility
4. Purchase - Price, where to buy
5. Comparison - vs other products
6. Results - Expected outcomes, timeline

Return ONLY a JSON array with this format:
[
  {{"question": "...", "answer": "...", "category": "Informational"}},
  {{"question": "...", "answer": "...", "category": "Usage"}},
  ...
]

Important:
- Answers should be helpful and based ONLY on the provided product data
- Questions should be natural, like a real customer would ask
- Minimum {min_questions} questions total
"""
    
    response = llm.generate(prompt, temperature=0.4)
    
    # Parse JSON from response
    import re
    match = re.search(r'\[.*\]', response, re.DOTALL)
    if match:
        qa_list = json.loads(match.group())
        if isinstance(qa_list, list):
            questions = []
            for item in qa_list:
                if isinstance(item, dict):
                    q = item.get("question", "")
                    a = item.get("answer", "")
                    c = item.get("category", "General")
                    if q and a:
                        questions.append((q, a, c))
            return questions
    
    return []


def _generate_questions_heuristic(
    product_data: Dict[str, Any], min_questions: int
) -> List[Tuple[str, str, str]]:
    """Fallback template-based question generation."""
    questions = []
    name = product_data.get("name", "this product")
    
    # Informational Questions
    questions.extend([
        (f"What is {name}?", 
         f"{name} is a skincare product containing {', '.join(product_data.get('key_ingredients', ['active ingredients']))}.", 
         "Informational"),
        (f"What are the key ingredients in {name}?",
         f"The key ingredients are {', '.join(product_data.get('key_ingredients', ['various active ingredients']))}.",
         "Informational"),
        (f"What are the benefits of {name}?",
         f"{name} provides {', '.join(product_data.get('benefits', ['multiple skincare benefits']))}.",
         "Informational"),
    ])
    
    # Usage Questions
    usage = product_data.get("usage_instructions", "Follow package directions")
    questions.extend([
        (f"How do I use {name}?",
         usage,
         "Usage"),
        (f"When should I apply {name}?",
         "Apply as part of your daily skincare routine. " + usage,
         "Usage"),
        (f"Can I use {name} with other products?",
         f"Yes, {name} can be layered with other skincare products. Apply after cleansing and before heavier creams.",
         "Usage"),
    ])
    
    # Safety Questions
    side_effects = product_data.get("side_effects", "No significant side effects reported")
    skin_types = product_data.get("skin_types", ["all skin types"])
    questions.extend([
        (f"Is {name} suitable for my skin type?",
         f"{name} is suitable for {', '.join(skin_types)}.",
         "Safety"),
        (f"Are there any side effects?",
         side_effects,
         "Safety"),
        (f"Is {name} safe for sensitive skin?",
         f"If you have sensitive skin, perform a patch test first. {side_effects}",
         "Safety"),
    ])
    
    # Purchase Questions
    price = product_data.get("price", "N/A")
    questions.extend([
        (f"How much does {name} cost?",
         f"{name} is priced at ₹{price}.",
         "Purchase"),
        (f"Where can I buy {name}?",
         f"You can purchase {name} from authorized retailers and online stores.",
         "Purchase"),
    ])
    
    # Results Questions
    questions.extend([
        (f"How long until I see results from {name}?",
         f"Most users notice improvements within 2-4 weeks of consistent use.",
         "Results"),
        (f"Will {name} work for dark spots?",
         f"Yes, {name} helps with brightening and fading dark spots due to its active ingredients.",
         "Results"),
    ])
    
    # Fill remaining with general questions
    questions = _augment_with_general_questions(questions, min_questions, name)
    
    return questions[:min_questions] if len(questions) > min_questions else questions


def _augment_with_general_questions(
    questions: List[Tuple[str, str, str]], target_count: int, product_name: str
) -> List[Tuple[str, str, str]]:
    """Fill up questions list with generic ones if under target count."""
    additional = [
        ("Is this product cruelty-free?",
         "Yes, we are committed to cruelty-free practices.",
         "Ethics"),
        ("Is the packaging recyclable?",
         "Yes, our packaging is designed to be recyclable.",
         "Sustainability"),
        ("What is the shelf life?",
         "The product has a shelf life of 12 months after opening.",
         "Usage"),
        ("Can I use it during pregnancy?",
         "Please consult your doctor before using new skincare products during pregnancy.",
         "Safety"),
        ("Does it contain parabens?",
         "No, this product is paraben-free.",
         "Ingredients"),
        ("Is it vegan?",
         "Yes, this formulation is 100% vegan.",
         "Ethics"),
        ("How should I store this product?",
         "Store in a cool, dry place away from direct sunlight.",
         "Usage"),
        ("Can men use this product?",
         "Absolutely! This product is suitable for all genders.",
         "Usage"),
    ]
    
    for q, a, c in additional:
        if len(questions) >= target_count:
            break
        if not any(q == existing[0] for existing in questions):
            questions.append((q, a, c))
    
    return questions
