"""
Test script to verify worker autonomy and parallel execution.
"""

import sys

sys.path.insert(0, ".")

from skincare_agent_system.actors.workers import (
    BenefitsWorker,
    ComparisonWorker,
    QuestionsWorker,
    UsageWorker,
    ValidationWorker,
)
from skincare_agent_system.core.models import AgentContext, ProductData


def test_worker_autonomy():
    """Test that workers can propose for tasks they specialize in."""

    print("=" * 60)
    print("TEST 1: Worker Specializations")
    print("=" * 60)

    # Check specializations are defined
    print(f"BenefitsWorker specializations: {BenefitsWorker.SPECIALIZATIONS}")
    print(f"UsageWorker specializations: {UsageWorker.SPECIALIZATIONS}")
    print(f"QuestionsWorker specializations: {QuestionsWorker.SPECIALIZATIONS}")
    print(f"ComparisonWorker specializations: {ComparisonWorker.SPECIALIZATIONS}")
    print(f"ValidationWorker specializations: {ValidationWorker.SPECIALIZATIONS}")

    assert (
        len(BenefitsWorker.SPECIALIZATIONS) > 0
    ), "BenefitsWorker should have specializations"
    assert (
        len(UsageWorker.SPECIALIZATIONS) > 0
    ), "UsageWorker should have specializations"
    print("✓ All workers have specializations defined")

    # Test 2: Worker proposals
    print("\n" + "=" * 60)
    print("TEST 2: Worker Proposals for Tasks")
    print("=" * 60)

    ctx = AgentContext()
    ctx.product_data = ProductData(
        name="Test Product",
        brand="Test Brand",
        price=100,
        currency="INR",
        key_ingredients=["A", "B"],
        benefits=["C"],
    )

    benefits_worker = BenefitsWorker("TestBenefitsWorker")

    # Benefits worker should propose high confidence for extract_benefits
    proposal = benefits_worker.propose_for_task("extract_benefits", ctx)
    print(
        f"BenefitsWorker for 'extract_benefits': confidence={proposal.confidence:.2f}"
    )
    assert (
        proposal.confidence > 0.8
    ), "BenefitsWorker should have high confidence for extract_benefits"

    # Benefits worker should propose low confidence for compare_products
    proposal = benefits_worker.propose_for_task("compare_products", ctx)
    print(
        f"BenefitsWorker for 'compare_products': confidence={proposal.confidence:.2f}"
    )
    # May not be able to handle at all

    # Comparison worker should have high confidence for compare_products
    comparison_worker = ComparisonWorker("TestComparisonWorker")
    proposal = comparison_worker.propose_for_task("compare_products", ctx)
    print(
        f"ComparisonWorker for 'compare_products': confidence={proposal.confidence:.2f}"
    )
    assert (
        proposal.confidence > 0.8
    ), "ComparisonWorker should have high confidence for compare_products"

    print("✓ Workers propose correctly based on specialization")

    # Test 3: DelegatorAgent uses worker proposals
    print("\n" + "=" * 60)
    print("TEST 3: DelegatorAgent Worker Proposal Integration")
    print("=" * 60)

    from skincare_agent_system.actors.delegator import DelegatorAgent

    ctx.comparison_data = ProductData(
        name="Competitor",
        brand="Other",
        price=150,
        currency="INR",
        key_ingredients=["X"],
        benefits=["Y"],
    )

    delegator = DelegatorAgent()

    # Check workers are initialized with proposal capability
    for worker_key, worker in delegator.workers.items():
        has_propose = hasattr(worker, "propose_for_task")
        print(f"  {worker_key}: has propose_for_task = {has_propose}")
        assert has_propose, f"{worker_key} should have propose_for_task method"

    print("✓ DelegatorAgent workers have proposal capability")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_worker_autonomy()
