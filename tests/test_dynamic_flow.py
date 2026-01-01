import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skincare_agent_system.agent_implementations import (
    AnalysisAgent,
    DataAgent,
    GenerationAgent,
    ValidationAgent,
)
from skincare_agent_system.data.products import GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT
from skincare_agent_system.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    ProductData,
)
from skincare_agent_system.orchestrator import Orchestrator

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestDynamicFlow")


class FlakyDataAgent(DataAgent):
    """
    Simulates fetching incomplete data first, then full data on retry.
    Using Strict Pydantic Models.
    """

    def __init__(self, name):
        super().__init__(name)
        self.call_count = 0

    def run(self, context: AgentContext) -> AgentResult:
        logger.info(f"FlakyDataAgent run #{self.call_count + 1}")
        self.call_count += 1

        # Super simple simulation
        raw_data = GLOWBOOST_PRODUCT.copy()
        raw_comp = RADIANCE_PLUS_PRODUCT.copy()

        # Map fields to match ProductData schema
        if "how_to_use" in raw_data:
            raw_data["usage_instructions"] = raw_data.pop("how_to_use")
        if "how_to_use" in raw_comp:
            raw_comp["usage_instructions"] = raw_comp.pop("how_to_use")

        if self.call_count == 1:
            # First run: Remove key_ingredients
            logger.info("❌ Simulating MISSING DATA (key_ingredients removed)")
            # In Pydantic model this is a list, so we set it to empty list to simulate missing data
            # ValidationAgent checks "if not context.product_data.key_ingredients"
            raw_data["key_ingredients"] = []

        # Create Typed Objects
        context.product_data = ProductData(**raw_data)
        context.comparison_data = ProductData(**raw_comp)

        # Mirror DataAgent behavior: Clear artifacts
        context.analysis_results = None
        context.generated_questions = []
        context.is_valid = False
        context.validation_errors = []

        return self.create_result(AgentStatus.CONTINUE, context, "Data loaded")


def main():
    print("TESTING DYNAMIC FLOW: Validation Fail -> Retry -> Success")

    orchestrator = Orchestrator()

    # Register agents, but swap DataAgent with FlakyDataAgent
    orchestrator.register_agent(FlakyDataAgent("DataAgent"))
    orchestrator.register_agent(AnalysisAgent("AnalysisAgent"))
    orchestrator.register_agent(ValidationAgent("ValidationAgent"))
    orchestrator.register_agent(GenerationAgent("GenerationAgent"))

    context = orchestrator.run()

    print("\nEXECUTION HISTORY:")
    for step in context.execution_history:
        print(f" -> {step}")

    # Check if we looped
    # Expected: Data -> Analysis -> Validation(Fail) -> Data -> Analysis -> Validation(Pass) -> Generation

    expected_steps = [
        "Running DataAgent",
        "Running AnalysisAgent",
        "Running ValidationAgent",
        # Retry loop
        "Running DataAgent",
        "Running AnalysisAgent",
        "Running ValidationAgent",
        "Running GenerationAgent",
    ]

    if context.execution_history == expected_steps:
        print("\n✅ TEST PASSED: Dynamic flow verified!")
    else:
        print(
            f"\n❌ TEST FAILED: Sequence mismatch.\nExpected: {expected_steps}\nGot: {context.execution_history}"
        )


if __name__ == "__main__":
    main()
