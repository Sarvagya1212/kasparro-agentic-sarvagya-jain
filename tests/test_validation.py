import pytest
from skincare_agent_system.actors.workers import ValidationWorker
from skincare_agent_system.core.models import (
    GlobalContext,
    AgentStatus,
    ProductData,
    ProcessingStage,
    ContentSchema
)

def test_validation_min_questions():
    worker = ValidationWorker("Val")
    context = GlobalContext()
    context.product_input = ProductData(
        name="ValidProduct", 
        brand="TestBrand", 
        key_ingredients=["X"], 
        benefits=["Y"],
        skin_types=["All"]
    )
    context.stage = ProcessingStage.VERIFICATION

    # Case 1: Too few questions
    context.generated_content.faq_questions = [("Q", "A", "C")] * 14
    result = worker.run(context)
    
    assert result.status == AgentStatus.VALIDATION_FAILED
    assert context.is_valid is False
    assert any("FAQ count" in e for e in context.errors) or "Rejection" in result.message

    # Case 2: Enough questions
    context.generated_content.faq_questions = [("Q", "A", "C")] * 15
    # Reset errors from previous run
    context.errors = [] 
    
    result = worker.run(context)
    
    assert result.status == AgentStatus.COMPLETE
    assert context.is_valid is True
    assert not context.errors
