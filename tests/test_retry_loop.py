"""
Test: Verify RETRY loop-back when ValidationAgent detects insufficient FAQ questions.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skincare_agent_system.agent_implementations import (  # noqa: E402
    AnalysisAgent,
    DataAgent,
    GenerationAgent,
    ValidationAgent,
)
from skincare_agent_system.models import (  # noqa: E402
    AgentContext,
    AgentResult,
    AgentStatus,
)
from skincare_agent_system.orchestrator import Orchestrator  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestRetryLoop")


class InsufficientFAQAnalysisAgent(AnalysisAgent):
    """
    Simulates an AnalysisAgent that generates fewer than 5 questions on first run.
    """

    def __init__(self, name):
        super().__init__(name)
        self.call_count = 0

    def run(self, context: AgentContext) -> AgentResult:
        self.call_count += 1
        logger.info(f"InsufficientFAQAnalysisAgent run #{self.call_count}")

        # Run parent logic first
        result = super().run(context)

        if self.call_count == 1:
            # First run: Truncate questions to trigger RETRY
            logger.info("❌ Simulating insufficient FAQ (only 3 questions)")
            context.generated_questions = context.generated_questions[:3]
            result.context = context
        else:
            # Second run: Full questions
            logger.info("✅ Returning full FAQ set")

        return result


def main():
    print("TESTING RETRY LOOP-BACK: Insufficient FAQ -> RETRY -> Success")

    orchestrator = Orchestrator()

    # Register agents with our mock
    orchestrator.register_agent(DataAgent("DataAgent"))
    orchestrator.register_agent(InsufficientFAQAnalysisAgent("AnalysisAgent"))
    orchestrator.register_agent(ValidationAgent("ValidationAgent"))
    orchestrator.register_agent(GenerationAgent("GenerationAgent"))

    context = orchestrator.run()

    print("\nEXECUTION HISTORY:")
    for step in context.execution_history:
        print(f" -> {step}")

    # Verify we looped back
    analysis_runs = sum(1 for s in context.execution_history if "AnalysisAgent" in s)

    if analysis_runs >= 2:
        print(
            f"\n✅ TEST PASSED: AnalysisAgent ran {analysis_runs} times "
            "(loop-back verified)"
        )
    else:
        print(
            f"\n❌ TEST FAILED: Expected AnalysisAgent to run >= 2 times, "
            f"got {analysis_runs}"
        )


if __name__ == "__main__":
    main()
