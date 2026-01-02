import pytest
from unittest.mock import MagicMock, patch
from skincare_agent_system.actors.workers import (
    ComparisonWorker,
    QuestionsWorker,
    UsageWorker,
    ValidationWorker,
)
from skincare_agent_system.core.models import (
    GlobalContext,
    AgentStatus,
    ProductData,
    ProcessingStage,
)

@pytest.fixture
def context():
    ctx = GlobalContext()
    ctx.product_input = ProductData(
        name="TestCream",
        brand="TestBrand",
        key_ingredients=["Water"],
        benefits=["Hydration"],
        price=10.0,
        skin_types=["All"],
        category="moisturizer"
    )
    ctx.comparison_input = ProductData(
        name="OtherCream", 
        brand="OtherBrand", 
        key_ingredients=["Oil"], 
        price=20.0,
        skin_types=["Dry"],
        category="moisturizer"
    )
    ctx.stage = ProcessingStage.INGEST
    return ctx

def test_usage_worker(context):
    worker = UsageWorker("Use")
    # Simulate INGEST stage
    context.stage = ProcessingStage.INGEST
    
    # Pre-check can_handle
    assert worker.can_handle(context) is True
    
    result = worker.run(context)
    
    assert result.status == AgentStatus.COMPLETE
    assert context.generated_content.usage != ""
    assert "Apply" in context.generated_content.usage

@patch("skincare_agent_system.logic_blocks.question_generator.get_provider")
def test_questions_worker(mock_get_provider, context):
    # Setup mock provider
    mock_provider = MagicMock()
    mock_provider.generate_faq.return_value = [
        ("Q1", "A1", "General"), ("Q2", "A2", "General"), 
        ("Q3", "A3", "General"), ("Q4", "A4", "General"),
        ("Q5", "A5", "General"), ("Q6", "A6", "General"),
        ("Q7", "A7", "General"), ("Q8", "A8", "General"),
        ("Q9", "A9", "General"), ("Q10", "A10", "General"),
        ("Q11", "A11", "General"), ("Q12", "A12", "General"),
        ("Q13", "A13", "General"), ("Q14", "A14", "General"),
        ("Q15", "A15", "General"), ("Q16", "A16", "General")
    ] # 16 questions to pass threshold of 15
    mock_provider.name = "MockProvider"
    mock_get_provider.return_value = mock_provider

    worker = QuestionsWorker("Quest")
    context.stage = ProcessingStage.SYNTHESIS
    
    assert worker.can_handle(context) is True
    
    result = worker.run(context)
    
    assert result.status == AgentStatus.COMPLETE
    assert len(context.generated_content.faq_questions) >= 15

def test_comparison_worker(context):
    worker = ComparisonWorker("Comp")
    context.stage = ProcessingStage.DRAFTING
    
    assert worker.can_handle(context) is True
    
    # Patch the provider factory globally in infrastructure 
    # This works because get_provider calls return a new instance, 
    # but we are patching the get_provider function itself.
    
    with patch("skincare_agent_system.infrastructure.providers.get_provider") as mock_prov_getter:
        mock_prov_getter.return_value.generate.side_effect = Exception("LLM Down")
        
        result = worker.run(context)
        
        assert result.status == AgentStatus.COMPLETE
        assert context.generated_content.comparison is not None
        assert "price_difference" in context.generated_content.comparison.get("analysis", {})
