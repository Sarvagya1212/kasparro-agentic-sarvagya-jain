import pytest

from skincare_agent_system.actors.workers import ValidationWorker
from skincare_agent_system.core.models import (
    AgentContext,
    AgentStatus,
    AnalysisResults,
    ProductData,
)


def test_validation_min_questions():
    worker = ValidationWorker("Val")
    context = AgentContext()
    context.product_data = ProductData(
        name="ValidProduct", brand="TestBrand", key_ingredients=["X"], benefits=["Y"]
    )
    context.analysis_results = AnalysisResults(
        benefits=["Y"], usage="Use it", comparison={}
    )

    # Case 1: Too few questions
    context.generated_questions = [("Q", "A", "C")] * 14
    result = worker.run(context)
    # result status is COMPLETE but context.is_valid should be False
    assert context.is_valid is False
    assert "FAQ must have 15+ questions" in str(context.validation_errors)

    # Case 2: Enough questions
    context.generated_questions = [("Q", "A", "C")] * 15
    result = worker.run(context)
    assert context.is_valid is True
    assert not context.validation_errors
