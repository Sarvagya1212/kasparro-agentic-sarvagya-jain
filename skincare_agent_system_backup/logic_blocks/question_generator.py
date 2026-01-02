"""
Question Generator Block - Generates categorized questions for FAQ.
"""

from typing import Any, Dict, List, Tuple


def generate_questions_by_category(
    product_data: Dict[str, Any], min_questions: int = 15
) -> List[Tuple[str, str, str]]:
    """
    Generate categorized questions and answers for a product.

    Args:
        product_data: Product information dictionary
        min_questions: Minimum number of questions to generate

    Returns:
        List of tuples: (question, answer, category)
    """
    questions = []

    # Informational Questions
    questions.extend(_generate_informational_questions(product_data))

    # Usage Questions
    questions.extend(_generate_usage_questions(product_data))

    # Safety Questions
    questions.extend(_generate_safety_questions(product_data))

    # Purchase Questions
    questions.extend(_generate_purchase_questions(product_data))

    # Comparison Questions
    questions.extend(_generate_comparison_questions(product_data))

    # Results Questions
    questions.extend(_generate_results_questions(product_data))

    # Ensure minimum count is met
    if len(questions) < min_questions:
        questions = _augment_with_general_questions(
            questions, min_questions, product_data.get("name", "this product")
        )

    return questions[:min_questions] if len(questions) > min_questions else questions


def _augment_with_general_questions(
    questions: List[Tuple[str, str, str]], target_count: int, product_name: str
) -> List[Tuple[str, str, str]]:
    """Fill up questions list with generic ones if under target count."""
    additional_questions = [
        (
            "Is this product cruelty-free?",
            "Yes, we are committed to cruelty-free practices.",
            "Ethics",
        ),
        (
            "Is the packaging recyclable?",
            "Yes, our packaging is designed to be recyclable.",
            "Sustainability",
        ),
        (
            "What is the shelf life?",
            "The product has a shelf life of 12 months after opening.",
            "Usage",
        ),
        (
            "Can I use it during pregnancy?",
            "Please consult your doctor before using new skincare products during pregnancy.",
            "Safety",
        ),
        (
            "Does it contain parabens?",
            "No, this product is paraben-free.",
            "Ingredients",
        ),
        ("Is it vegan?", "Yes, this formulation is 100% vegan.", "Ethics"),
        (
            "Do you ship internationally?",
            "Please check our shipping policy page for international delivery options.",
            "Purchase",
        ),
        (
            "What if I don't like it?",
            "We offer a 30-day satisfaction guarantee.",
            "Purchase",
        ),
        (
            "Can men use this?",
            "Yes, skincare is for everyone regardless of gender.",
            "Usage",
        ),
        (
            "Is it fragrance-free?",
            "Check the ingredients list, but generally we avoid artificial fragrances.",
            "Ingredients",
        ),
    ]

    current_count = len(questions)
    needed = target_count - current_count

    if needed <= 0:
        return questions

    # Filter out duplicates
    existing_qs = {q[0] for q in questions}

    for i in range(len(additional_questions)):
        if len(questions) >= target_count:
            break
        q, a, c = additional_questions[i]
        if q not in existing_qs:
            questions.append((q, a, c))

    return questions


def _generate_informational_questions(
    product_data: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """Generate informational questions."""
    questions = []
    name = product_data.get("name", "this product")

    # What is this product?
    category = product_data.get("category", "skincare product")
    questions.append(
        (
            f"What is {name}?",
            f"{name} is a {category} designed for skincare.",
            "Informational",
        )
    )

    # Key ingredients
    ingredients = product_data.get("key_ingredients", [])
    if ingredients:
        questions.append(
            (
                f"What are the key ingredients in {name}?",
                f"The key ingredients include {', '.join(ingredients)}.",
                "Informational",
            )
        )

    # Concentration
    if "concentration" in product_data:
        questions.append(
            (
                "What is the concentration of active ingredients?",
                f"This product contains {product_data['concentration']}.",
                "Informational",
            )
        )

    return questions


def _generate_usage_questions(
    product_data: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """Generate usage questions."""
    questions = []
    name = product_data.get("name", "this product")
    usage = product_data.get("how_to_use", "Apply as directed")

    questions.append((f"How do I use {name}?", usage, "Usage"))

    # Frequency
    questions.append(
        (
            "How often should I use this product?",
            (
                "For best results, use as part of your daily skincare "
                "routine. Follow the specific instructions on the packaging."
            ),
            "Usage",
        )
    )

    # Layering
    questions.append(
        (
            "Can I use this with other skincare products?",
            (
                "Yes, this product can be incorporated into your existing "
                "routine. Apply in order of thinnest to thickest consistency."
            ),
            "Usage",
        )
    )

    return questions


def _generate_safety_questions(
    product_data: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """Generate safety questions."""
    questions = []
    name = product_data.get("name", "this product")
    side_effects = product_data.get("side_effects", "None reported")

    questions.append(
        (f"Are there any side effects of using {name}?", side_effects, "Safety")
    )

    # Skin type suitability
    skin_types = product_data.get("skin_types", [])
    if skin_types:
        questions.append(
            (
                "Is this suitable for my skin type?",
                f"This product is formulated for {', '.join(skin_types)} skin types.",
                "Safety",
            )
        )

    # Patch test
    questions.append(
        (
            "Should I do a patch test?",
            (
                "Yes, we recommend doing a patch test before full "
                "application, especially if you have sensitive skin."
            ),
            "Safety",
        )
    )

    return questions


def _generate_purchase_questions(
    product_data: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """Generate purchase-related questions."""
    questions = []
    name = product_data.get("name", "this product")
    price = product_data.get("price", 0)

    questions.append(
        (f"How much does {name} cost?", f"The price is ₹{price}.", "Purchase")
    )

    # Size
    if "size" in product_data:
        questions.append(
            (
                "What size is the product?",
                f"This product comes in {product_data['size']} size.",
                "Purchase",
            )
        )

    # Value
    questions.append(
        (
            "Is this product worth the price?",
            (
                f"At ₹{price}, this product offers excellent value with "
                f"high-quality ingredients and proven results."
            ),
            "Purchase",
        )
    )

    return questions


def _generate_comparison_questions(
    product_data: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """Generate comparison questions."""
    questions = []
    name = product_data.get("name", "this product")

    questions.append(
        (
            f"How does {name} compare to other similar products?",
            (
                f"{name} stands out due to its unique formulation and "
                "concentration of active ingredients."
            ),
            "Comparison",
        )
    )

    questions.append(
        (
            "What makes this product different?",
            (
                "This product combines high-quality ingredients with an "
                "effective delivery system for optimal results."
            ),
            "Comparison",
        )
    )

    return questions


def _generate_results_questions(
    product_data: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    """Generate results-related questions."""
    questions = []
    name = product_data.get("name", "this product")
    benefits = product_data.get("benefits", [])

    questions.append(
        (
            "When will I see results?",
            (
                "Most users notice improvements within 2-4 weeks of "
                "consistent use. For best results, use as directed."
            ),
            "Results",
        )
    )

    if benefits:
        questions.append(
            (
                f"What results can I expect from {name}?",
                f"You can expect: {', '.join(benefits)}.",
                "Results",
            )
        )

    questions.append(
        (
            "How long does one bottle last?",
            "With regular use as directed, one bottle typically lasts 1-2 months.",
            "Results",
        )
    )

    return questions
