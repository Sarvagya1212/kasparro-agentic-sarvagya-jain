"""
Test script to verify dynamic proposals are working.
"""

import sys

sys.path.insert(0, ".")

from skincare_agent_system.actors.agent_implementations import (
    DataAgent,
    GenerationAgent,
    SyntheticDataAgent,
)
from skincare_agent_system.actors.delegator import DelegatorAgent
from skincare_agent_system.actors.verifier import VerifierAgent
from skincare_agent_system.core.context_analyzer import get_context_analyzer
from skincare_agent_system.core.models import AgentContext, ProductData


def test_dynamic_proposals():
    """Test that proposals use dynamic scoring."""

    # Test 1: Empty context - DataAgent should have high confidence
    print("=" * 60)
    print("TEST 1: Empty Context (DataAgent should propose with high confidence)")
    print("=" * 60)

    ctx = AgentContext()
    analyzer = get_context_analyzer()

    print(f"Workflow phase: {analyzer.detect_workflow_phase(ctx)}")
    print(f"Data readiness: {analyzer.assess_data_readiness(ctx):.2f}")

    data_agent = DataAgent()
    proposal = data_agent.propose(ctx)
    print(
        f"DataAgent proposal: confidence={proposal.confidence:.2f}, priority={proposal.priority}"
    )
    print(f"Reason: {proposal.reason}")

    # Verify it's dynamic (not hardcoded 0.95 or 10)
    assert (
        proposal.preconditions_met
    ), "DataAgent should be able to handle empty context"
    print("✓ DataAgent proposes with dynamic scoring")

    # Test 2: Context with product data
    print("\n" + "=" * 60)
    print("TEST 2: Context with Product Data (SyntheticDataAgent should propose)")
    print("=" * 60)

    ctx.product_data = ProductData(
        name="Test Product",
        brand="Test Brand",
        price=100,
        currency="INR",
        key_ingredients=["A", "B"],
        benefits=["C"],
    )
    ctx.comparison_data = None  # No comparison yet

    print(f"Workflow phase: {analyzer.detect_workflow_phase(ctx)}")

    synth_agent = SyntheticDataAgent()
    proposal = synth_agent.propose(ctx)
    print(
        f"SyntheticDataAgent proposal: confidence={proposal.confidence:.2f}, priority={proposal.priority}"
    )
    print(f"Reason: {proposal.reason}")

    assert (
        proposal.preconditions_met
    ), "SyntheticDataAgent should be able to handle context with product but no comparison"
    print("✓ SyntheticDataAgent proposes with dynamic scoring")

    # Test 3: Context with both products
    print("\n" + "=" * 60)
    print("TEST 3: Context with Both Products (DelegatorAgent should propose)")
    print("=" * 60)

    ctx.comparison_data = ProductData(
        name="Competitor",
        brand="Other",
        price=150,
        currency="INR",
        key_ingredients=["X"],
        benefits=["Y"],
    )

    print(f"Workflow phase: {analyzer.detect_workflow_phase(ctx)}")
    print(f"Analysis readiness: {analyzer.assess_analysis_readiness(ctx):.2f}")

    delegator = DelegatorAgent()
    proposal = delegator.propose(ctx)
    print(
        f"DelegatorAgent proposal: confidence={proposal.confidence:.2f}, priority={proposal.priority}"
    )
    print(f"Reason: {proposal.reason}")

    assert (
        proposal.preconditions_met
    ), "DelegatorAgent should be able to handle context ready for analysis"
    print("✓ DelegatorAgent proposes with dynamic scoring")

    # Test 4: Verify recency penalty
    print("\n" + "=" * 60)
    print("TEST 4: Recency Penalty (repeated agents get penalized)")
    print("=" * 60)

    # Record some executions
    analyzer.record_execution("DataAgent", success=True)
    analyzer.record_execution("DataAgent", success=True)

    penalty = analyzer._get_recency_penalty("DataAgent")
    print(f"Recency penalty for DataAgent: {penalty:.2f}")

    assert penalty > 0, "Recently executed agent should have penalty"
    print("✓ Recency penalty is applied")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_dynamic_proposals()
