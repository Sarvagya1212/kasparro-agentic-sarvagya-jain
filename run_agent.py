"""
Main entry point for Skincare Agent System.
Demonstrates the simplified multi-agent workflow.
"""

import json
import os
import sys

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


def load_product_data():
    """Load sample product data"""
    return {
        "name": "GlowBoost Vitamin C Serum",
        "brand": "GlowBoost",
        "concentration": "10%",
        "key_ingredients": ["Vitamin C", "Hyaluronic Acid", "Niacinamide"],
        "benefits": ["Brightening", "Anti-aging", "Hydration", "Even skin tone"],
        "price": 699.0,
        "currency": "INR",
        "skin_types": ["Oily", "Dry", "Combination"],
        "side_effects": "May cause mild tingling initially",
        "usage_instructions": "Apply 2-3 drops to clean face morning and evening"
    }


def load_comparison_data():
    """Load comparison product data"""
    return {
        "name": "RadiantGlow Vitamin C",
        "brand": "RadiantGlow",
        "concentration": "15%",
        "key_ingredients": ["Vitamin C", "Ferulic Acid"],
        "benefits": ["Brightening", "Antioxidant protection"],
        "price": 899.0,
        "currency": "INR",
        "skin_types": ["Normal", "Combination"],
    }


def main():
    print("=" * 60)
    print("🧴 Skincare Agent System - Simplified Version")
    print("=" * 60)
    
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
    
    for worker in workers:
        orchestrator.register_agent(worker)
        print(f"  ✓ Registered {worker.name}")
    
    print()
    
    # Load product data
    product_data = load_product_data()
    print(f"📦 Product: {product_data['name']}")
    print(f"   Brand: {product_data['brand']}")
    print(f"   Price: ₹{product_data['price']}")
    print()
    
    # Run workflow
    print("🚀 Starting workflow...")
    print("-" * 60)
    
    try:
        context = orchestrator.run(initial_product_data=product_data)
        
        print("-" * 60)
        print()
        
        # Show results
        if context.is_valid:
            print("✅ Workflow completed successfully!")
        else:
            print("⚠️  Workflow completed with validation errors:")
            for error in context.validation_errors:
                print(f"   - {error}")
        
        print()
        print("📊 Results Summary:")
        if context.analysis_results:
            print(f"   Benefits extracted: {len(context.analysis_results.benefits)}")
            print(f"   Usage instructions: {'Yes' if context.analysis_results.usage else 'No'}")
        print(f"   Questions generated: {len(context.generated_questions)}")
        print(f"   Execution steps: {len(context.execution_history)}")
        
        # Save outputs
        os.makedirs("output", exist_ok=True)
        
        # Save context summary
        summary = {
            "product": product_data["name"],
            "benefits": context.analysis_results.benefits if context.analysis_results else [],
            "usage": context.analysis_results.usage if context.analysis_results else "",
            "questions_count": len(context.generated_questions),
            "is_valid": context.is_valid,
            "validation_errors": context.validation_errors,
            "execution_history": context.execution_history
        }
        
        with open("output/run_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print()
        print("💾 Saved: output/run_summary.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
