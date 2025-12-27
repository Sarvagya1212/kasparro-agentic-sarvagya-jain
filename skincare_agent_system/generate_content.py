"""
Main pipeline script - Generates all required JSON outputs.
This demonstrates the full agentic automation system.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from data.products import GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT
from templates.faq_template import FAQTemplate
from templates.product_page_template import ProductPageTemplate
from templates.comparison_template import ComparisonTemplate
from logic_blocks.question_generator import generate_questions_by_category
from logic_blocks.benefits_block import extract_benefits
from logic_blocks.usage_block import extract_usage_instructions
from logic_blocks.comparison_block import (
    compare_ingredients,
    compare_prices,
    compare_benefits,
    determine_winner,
    generate_recommendation,
)


def generate_faq_page(product_data: dict, output_path: str = "output/faq.json"):
    """
    Generate FAQ page using question generator logic block and FAQ template.

    Args:
        product_data: Product information
        output_path: Path to save JSON output
    """
    print("\n" + "=" * 60)
    print("GENERATING FAQ PAGE")
    print("=" * 60)

    # Use logic block to generate questions
    qa_list = generate_questions_by_category(product_data, min_questions=15)

    # Prepare data for template
    template_data = {
        "product_name": product_data["name"],
        "qa_pairs": [(q, a) for q, a, c in qa_list],
        "categories": {},
        "timestamp": datetime.now().isoformat(),
    }

    # Categorize questions
    for i, (q, a, category) in enumerate(qa_list):
        if category not in template_data["categories"]:
            template_data["categories"][category] = []
        template_data["categories"][category].append(i)

    # Render using template
    template = FAQTemplate()
    output = template.render(template_data)

    # Save to JSON
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✓ Generated {len(qa_list)} questions")
    print(f"✓ Saved to: {output_path}")

    return output


def generate_product_page(product_data: dict, output_path: str = "output/product_page.json"):
    """
    Generate product page using benefits/usage logic blocks and product template.

    Args:
        product_data: Product information
        output_path: Path to save JSON output
    """
    print("\n" + "=" * 60)
    print("GENERATING PRODUCT PAGE")
    print("=" * 60)

    # Use logic blocks to extract/enhance data
    benefits = extract_benefits(product_data)
    usage = extract_usage_instructions(product_data)

    # Prepare data for template
    template_data = {
        "name": product_data["name"],
        "brand": product_data.get("brand", ""),
        "concentration": product_data.get("concentration", ""),
        "benefits": benefits,
        "ingredients": product_data.get("key_ingredients", []),
        "usage_instructions": usage,
        "price": product_data.get("price", 0),
        "currency": product_data.get("currency", "INR"),
        "size": product_data.get("size", ""),
        "skin_types": product_data.get("skin_types", []),
        "concerns": product_data.get("benefits", []),
        "side_effects": product_data.get("side_effects", "None reported"),
    }

    # Render using template
    template = ProductPageTemplate()
    output = template.render(template_data)

    # Save to JSON
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✓ Product: {product_data['name']}")
    print(f"✓ Saved to: {output_path}")

    return output


def generate_comparison_page(
    product_a: dict, product_b: dict, output_path: str = "output/comparison_page.json"
):
    """
    Generate comparison page using comparison logic blocks and comparison template.

    Args:
        product_a: First product (GlowBoost)
        product_b: Second product (fictional)
        output_path: Path to save JSON output
    """
    print("\n" + "=" * 60)
    print("GENERATING COMPARISON PAGE")
    print("=" * 60)

    # Use logic blocks for comparison
    ingredient_comp = compare_ingredients(product_a, product_b)
    price_comp = compare_prices(product_a, product_b)
    benefit_comp = compare_benefits(product_a, product_b)
    winners = determine_winner(product_a, product_b)
    recommendation = generate_recommendation(product_a, product_b)

    # Build differences list
    differences = [
        {
            "aspect": "Ingredients",
            "details": f"Common: {', '.join(ingredient_comp['common_ingredients'])}. "
            f"{product_a['name']} unique: {', '.join(ingredient_comp['unique_to_a'])}. "
            f"{product_b['name']} unique: {', '.join(ingredient_comp['unique_to_b'])}.",
        },
        {
            "aspect": "Price",
            "details": f"₹{price_comp['difference']} difference ({price_comp['percentage_difference']}%). "
            f"{price_comp['cheaper_product']} is more affordable.",
        },
        {
            "aspect": "Benefits",
            "details": f"Common: {', '.join(benefit_comp['common_benefits'])}. "
            f"Unique benefits vary between products.",
        },
    ]

    # Prepare data for template
    template_data = {
        "primary": product_a,
        "other": product_b,
        "differences": differences,
        "recommendation": recommendation,
        "winner_categories": winners,
    }

    # Render using template
    template = ComparisonTemplate()
    output = template.render(template_data)

    # Save to JSON
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✓ Comparing: {product_a['name']} vs {product_b['name']}")
    print(f"✓ Saved to: {output_path}")

    return output


def main():
    """
    Main pipeline - generates all 3 required JSON outputs.
    This is the autonomous agentic system in action.
    """
    print("\n" + "=" * 70)
    print("KASPARRO MULTI-AGENT CONTENT GENERATION SYSTEM")
    print("=" * 70)
    print("\nInput: GlowBoost Vitamin C Serum (from assignment specification)")
    print("Output: 3 JSON files (FAQ, Product Page, Comparison)")
    print("\nPipeline: Data → Logic Blocks → Templates → JSON Output")

    # Generate all 3 pages
    faq_output = generate_faq_page(GLOWBOOST_PRODUCT)
    product_output = generate_product_page(GLOWBOOST_PRODUCT)
    comparison_output = generate_comparison_page(GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT)

    # Summary
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print("\n✓ All 3 JSON files generated successfully:")
    print("  1. output/faq.json")
    print("  2. output/product_page.json")
    print("  3. output/comparison_page.json")
    print("\n✓ System demonstrates:")
    print("  - Clear agent boundaries (templates, logic blocks)")
    print("  - Reusable logic blocks (benefits, usage, comparison, questions)")
    print("  - Custom template system (not LLM prompts)")
    print("  - Structured JSON output")
    print("  - Autonomous pipeline execution")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
