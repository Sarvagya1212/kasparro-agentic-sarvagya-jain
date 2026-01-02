"""
Main entry point for Skincare Agent System.
Generates the 3 required output files: faq.json, product_page.json, comparison_page.json
"""

import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skincare_agent_system.core.orchestrator import Orchestrator
from skincare_agent_system.actors.workers import (
    BenefitsWorker,
    UsageWorker,
    QuestionsWorker,
    ComparisonWorker,
    ValidationWorker,
)
from skincare_agent_system.templates.faq_template import FAQTemplate
from skincare_agent_system.templates.product_page_template import ProductPageTemplate
from skincare_agent_system.templates.comparison_template import ComparisonTemplate


def load_product_data():
    """Load the primary product data (GlowBoost) as specified in assignment"""
    return {
        "name": "GlowBoost Vitamin C Serum",
        "brand": "GlowBoost",
        "concentration": "10% Vitamin C",
        "key_ingredients": ["Vitamin C", "Hyaluronic Acid"],
        "benefits": ["Brightening", "Fades dark spots"],
        "price": 699.0,
        "currency": "INR",
        "skin_types": ["Oily", "Combination"],
        "side_effects": "Mild tingling for sensitive skin",
        "usage_instructions": "Apply 2-3 drops in the morning before sunscreen"
    }


def load_comparison_product():
    """Load fictional Product B for comparison"""
    return {
        "name": "RadiantGlow Vitamin C Cream",
        "brand": "RadiantGlow",
        "concentration": "15% Vitamin C",
        "key_ingredients": ["Vitamin C", "Ferulic Acid", "Vitamin E"],
        "benefits": ["Brightening", "Antioxidant protection", "Fine line reduction"],
        "price": 899.0,
        "currency": "INR",
        "skin_types": ["Normal", "Dry", "Combination"],
        "side_effects": "May cause dryness initially",
        "usage_instructions": "Apply morning and evening to clean skin"
    }


def generate_faq_json(context, product_name):
    """Generate FAQ JSON using the FAQ template"""
    template = FAQTemplate()
    
    # Convert questions from tuples to qa_pairs format
    qa_pairs = []
    for q in context.generated_questions:
        if isinstance(q, tuple) and len(q) >= 2:
            qa_pairs.append((q[0], q[1]))
        elif isinstance(q, dict):
            qa_pairs.append((q.get("question", ""), q.get("answer", "")))
    
    data = {
        "product_name": product_name,
        "qa_pairs": qa_pairs,
        "timestamp": datetime.now().isoformat()
    }
    
    return template.render(data)


def generate_product_page_json(product_data, context):
    """Generate Product Page JSON using the ProductPage template"""
    template = ProductPageTemplate()
    
    # Use extracted benefits if available, else use original
    benefits = (
        context.analysis_results.benefits 
        if context.analysis_results and context.analysis_results.benefits 
        else product_data.get("benefits", [])
    )
    
    # Use extracted usage if available, else use original
    usage = (
        context.analysis_results.usage 
        if context.analysis_results and context.analysis_results.usage 
        else product_data.get("usage_instructions", "")
    )
    
    data = {
        "name": product_data["name"],
        "brand": product_data.get("brand", ""),
        "concentration": product_data.get("concentration", ""),
        "benefits": benefits,
        "ingredients": product_data.get("key_ingredients", []),
        "usage_instructions": usage,
        "price": product_data.get("price", 0),
        "currency": product_data.get("currency", "INR"),
        "skin_types": product_data.get("skin_types", []),
        "concerns": ["Dull skin", "Dark spots", "Uneven tone"],
        "side_effects": product_data.get("side_effects", "")
    }
    
    return template.render(data)


def generate_comparison_json(product_a, product_b, context):
    """Generate Comparison Page JSON using the Comparison template"""
    template = ComparisonTemplate()
    
    # Get comparison results from context
    comparison_data = {}
    if context.analysis_results and context.analysis_results.comparison:
        comparison_data = context.analysis_results.comparison
    
    data = {
        "primary": {
            "name": product_a["name"],
            "price": product_a.get("price", 0),
            "ingredients": product_a.get("key_ingredients", []),
            "skin_types": product_a.get("skin_types", []),
            "benefits": product_a.get("benefits", [])
        },
        "other": {
            "name": product_b["name"],
            "price": product_b.get("price", 0),
            "ingredients": product_b.get("key_ingredients", []),
            "skin_types": product_b.get("skin_types", []),
            "benefits": product_b.get("benefits", [])
        },
        "differences": comparison_data.get("differences", [
            {"aspect": "Price", "winner": "GlowBoost", "reason": "₹200 cheaper"},
            {"aspect": "Ingredients", "winner": "RadiantGlow", "reason": "More antioxidants"},
            {"aspect": "Skin types", "winner": "RadiantGlow", "reason": "Wider compatibility"}
        ]),
        "recommendation": comparison_data.get("recommendation", 
            "GlowBoost is ideal for budget-conscious users with oily skin. "
            "RadiantGlow offers more comprehensive antioxidant protection."
        ),
        "winner_categories": comparison_data.get("winners", {
            "price": "GlowBoost",
            "ingredients": "RadiantGlow",
            "overall": "Tie - depends on skin type and budget"
        })
    }
    
    return template.render(data)


def main():
    print("=" * 60)
    print("🧴 Skincare Agent System - Multi-Agent Content Generation")
    print("=" * 60)
    
    # Load product data
    product_data = load_product_data()
    comparison_product = load_comparison_product()
    
    print(f"\n📦 Primary Product: {product_data['name']}")
    print(f"📦 Comparison Product: {comparison_product['name']}")
    
    # Create orchestrator
    orchestrator = Orchestrator()
    
    # Register workers
    workers = [
        BenefitsWorker("BenefitsWorker"),
        UsageWorker("UsageWorker"),
        QuestionsWorker("QuestionsWorker"),
        ComparisonWorker("ComparisonWorker"),
        ValidationWorker("ValidationWorker"),
    ]
    
    print("\n🤖 Registered Agents:")
    for worker in workers:
        orchestrator.register_agent(worker)
        print(f"   ✓ {worker.name}")
    
    # Set comparison data on context
    from skincare_agent_system.core.models import ProductData
    orchestrator.context.comparison_data = ProductData(**comparison_product)
    
    # Run workflow
    print("\n🚀 Starting agent workflow...")
    print("-" * 60)
    
    try:
        context = orchestrator.run(initial_product_data=product_data)
        
        print("-" * 60)
        
        # Show results
        if context.is_valid:
            print("\n✅ Workflow completed successfully!")
        else:
            print("\n⚠️  Workflow completed with validation errors:")
            for error in context.validation_errors:
                print(f"   - {error}")
        
        print(f"\n📊 Agent Results:")
        if context.analysis_results:
            print(f"   Benefits extracted: {len(context.analysis_results.benefits)}")
            print(f"   Usage instructions: {'✓' if context.analysis_results.usage else '✗'}")
        print(f"   Questions generated: {len(context.generated_questions)}")
        print(f"   Execution steps: {len(context.execution_history)}")
        
        # Generate output files
        os.makedirs("output", exist_ok=True)
        
        # 1. Generate FAQ JSON
        faq_json = generate_faq_json(context, product_data["name"])
        with open("output/faq.json", "w") as f:
            json.dump(faq_json, f, indent=2)
        print(f"\n💾 Generated: output/faq.json ({faq_json['total_questions']} Q&As)")
        
        # 2. Generate Product Page JSON
        product_json = generate_product_page_json(product_data, context)
        with open("output/product_page.json", "w") as f:
            json.dump(product_json, f, indent=2)
        print(f"💾 Generated: output/product_page.json")
        
        # 3. Generate Comparison Page JSON
        comparison_json = generate_comparison_json(product_data, comparison_product, context)
        with open("output/comparison_page.json", "w") as f:
            json.dump(comparison_json, f, indent=2)
        print(f"💾 Generated: output/comparison_page.json")
        
        print("\n" + "=" * 60)
        print("✅ All 3 required output files generated successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
