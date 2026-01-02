"""
Main entry point for Skincare Agent System.
Loads product data from config, runs agents, generates JSON outputs.
"""

import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skincare_agent_system.core.models import (
    GlobalContext,
    ProductData,
    ContentSchema,
    ProcessingStage,
)
from skincare_agent_system.core.orchestrator import Orchestrator
from skincare_agent_system.actors.workers import (
    UsageWorker,
    QuestionsWorker,
    ComparisonWorker,
    ValidationWorker,
)
from skincare_agent_system.templates.faq_template import FAQTemplate
from skincare_agent_system.templates.product_page_template import ProductPageTemplate
from skincare_agent_system.templates.comparison_template import ComparisonTemplate


def load_config() -> GlobalContext:
    """
    Load product data from external config file.
    Config path can be overridden via RUN_CONFIG env variable.
    """
    config_path = os.getenv("RUN_CONFIG", "config/run_config.json")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            f"Create config/run_config.json or set RUN_CONFIG env variable."
        )
    
    with open(config_path, "r") as f:
        data = json.load(f)
    
    # Validate and load product data
    product = ProductData(**data["product"])
    comparison = ProductData(**data["comparison_product"]) if "comparison_product" in data else None
    
    return GlobalContext(
        product_input=product,
        comparison_input=comparison,
        stage=ProcessingStage.INGEST
    )


def generate_faq_json(context: GlobalContext) -> dict:
    """Generate FAQ JSON using the FAQ template."""
    template = FAQTemplate()
    
    qa_pairs = []
    for q in context.generated_content.faq_questions:
        if isinstance(q, tuple) and len(q) >= 3:
            qa_pairs.append((q[0], q[1], q[2]))
        elif isinstance(q, tuple) and len(q) == 2:
            qa_pairs.append((q[0], q[1], "General"))
    
    data = {
        "product_name": context.product_input.name,
        "qa_pairs": qa_pairs,
        "timestamp": datetime.now().isoformat()
    }
    
    return template.render(data)



def generate_product_page_json(context: GlobalContext) -> dict:
    """Generate Product Page JSON using the ProductPage template."""
    template = ProductPageTemplate()
    
    product = context.product_input
    
    data = {
        "name": product.name,
        "brand": product.brand,
        "concentration": product.concentration or "",
        "benefits": product.benefits,
        "ingredients": product.key_ingredients,
        "usage_instructions": context.generated_content.usage or product.usage_instructions,
        "price": product.price or 0,
        "currency": product.currency,
        "skin_types": product.skin_types,
        "concerns": ["Dull skin", "Dark spots", "Uneven tone"],
        "side_effects": product.side_effects or ""
    }
    
    return template.render(data)


def generate_comparison_json(context: GlobalContext) -> dict:
    """Generate Comparison Page JSON using the Comparison template."""
    template = ComparisonTemplate()
    
    product_a = context.product_input
    product_b = context.comparison_input
    comparison_data = context.generated_content.comparison or {}
    
    data = {
        "primary": {
            "name": product_a.name,
            "price": product_a.price or 0,
            "ingredients": product_a.key_ingredients,
            "skin_types": product_a.skin_types,
            "benefits": product_a.benefits
        },
        "other": {
            "name": product_b.name if product_b else "N/A",
            "price": product_b.price if product_b else 0,
            "ingredients": product_b.key_ingredients if product_b else [],
            "skin_types": product_b.skin_types if product_b else [],
            "benefits": product_b.benefits if product_b else []
        },
        "differences": comparison_data.get("differences", []),
        # Use the actual generated recommendation from comparison_block
        "recommendation": comparison_data.get("recommendation", "No comparison available."),
        "winner_categories": comparison_data.get("winner", {})
    }
    
    return template.render(data)



def main():
    print("=" * 60)
    print("🧴 Skincare Agent System")
    print("=" * 60)
    
    # Load from external config
    print("\n📂 Loading config...")
    try:
        context = load_config()
        print(f"   ✓ Product: {context.product_input.name}")
        if context.comparison_input:
            print(f"   ✓ Comparison: {context.comparison_input.name}")
    except Exception as e:
        print(f"   ✗ Failed to load config: {e}")
        return 1
    
    # Create orchestrator
    orchestrator = Orchestrator(max_steps=15)
    
    # Register workers
    workers = [
        UsageWorker("UsageWorker"),
        QuestionsWorker("QuestionsWorker"),
        ComparisonWorker("ComparisonWorker"),
        ValidationWorker("ValidationWorker"),
    ]
    
    print("\n🤖 Registered Agents:")
    for worker in workers:
        orchestrator.register_agent(worker)
        print(f"   ✓ {worker.name}")
    
    # Run workflow
    print("\n🚀 Starting workflow...")
    print("-" * 60)
    
    try:
        final_context = orchestrator.run(context)
        
        print("-" * 60)
        
        # Display results
        if final_context.is_valid:
            print("\n✅ Workflow completed successfully!")
        else:
            print("\n⚠️  Workflow completed with validation errors:")
            for error in final_context.errors:
                print(f"   - {error}")
        
        print(f"\n📊 Results:")
        print(f"   Stage: {final_context.stage.value}")
        print(f"   Usage: {'✓' if final_context.generated_content.usage else '✗'}")
        print(f"   FAQs: {len(final_context.generated_content.faq_questions)}")
        print(f"   Steps: {len(final_context.execution_history)}")
        
        # Generate output files
        os.makedirs("output", exist_ok=True)
        
        faq_json = generate_faq_json(final_context)
        with open("output/faq.json", "w") as f:
            json.dump(faq_json, f, indent=2)
        print(f"\n💾 output/faq.json ({faq_json.get('total_questions', 0)} Q&As)")
        
        product_json = generate_product_page_json(final_context)
        with open("output/product_page.json", "w") as f:
            json.dump(product_json, f, indent=2)
        print("💾 output/product_page.json")
        
        comparison_json = generate_comparison_json(final_context)
        with open("output/comparison_page.json", "w") as f:
            json.dump(comparison_json, f, indent=2)
        print("💾 output/comparison_page.json")
        
        print("\n" + "=" * 60)
        print("✅ All outputs generated!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
