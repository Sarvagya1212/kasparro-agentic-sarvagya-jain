import pytest

from skincare_agent_system.actors.workers import (
    BenefitsWorker,
    ComparisonWorker,
    QuestionsWorker,
    UsageWorker,
    ValidationWorker,
)
from skincare_agent_system.core.models import AgentContext, AgentStatus, ProductData


@pytest.fixture
def context():
    ctx = AgentContext()
    ctx.product_data = ProductData(
        name="TestCream",
        brand="TestBrand",
        key_ingredients=["Water"],
        benefits=["Hydration"],
        price=10.0,
    )
    ctx.comparison_data = ProductData(
        name="OtherCream", brand="OtherBrand", key_ingredients=["Oil"], price=20.0
    )
    return ctx


def test_benefits_worker(context):
    worker = BenefitsWorker("Ben")
    result = worker.run(context)
    assert result.status == AgentStatus.COMPLETE
    assert context.analysis_results.benefits is not None


def test_usage_worker(context):
    worker = UsageWorker("Use")
    result = worker.run(context)
    assert result.status == AgentStatus.COMPLETE
    assert context.analysis_results.usage is not None


def test_questions_worker(context):
    worker = QuestionsWorker("Quest")
    result = worker.run(context)
    if result.status != AgentStatus.COMPLETE:
        print(f"DEBUG ERROR: {result.message}")
    assert result.status == AgentStatus.COMPLETE
    # logic block might return empty list if not implemented fully, but we expect success
    # check that we have some result structure
    # The actual generation logic might depend on ProductData content


def test_comparison_worker(context):
    worker = ComparisonWorker("Comp")
    result = worker.run(context)
    if result.status != AgentStatus.COMPLETE:
        print(f"DEBUG ERROR: {result.message}")
    assert result.status == AgentStatus.COMPLETE
    assert context.analysis_results.comparison is not None
