"""All worker agents in one file for simplicity"""

import logging
from typing import Any, Dict, List, Optional

from ..core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    AnalysisResults,
    TaskDirective,
)

# Import Logic Blocks directly
from ..logic_blocks.benefits_block import extract_benefits
from ..logic_blocks.comparison_block import (
    compare_benefits,
    compare_ingredients,
    compare_prices,
    determine_winner,
    generate_recommendation,
)
from ..logic_blocks.question_generator import (
    _augment_with_general_questions,
    generate_questions_by_category,
)
from ..logic_blocks.usage_block import extract_usage_instructions
from .base_agent import BaseAgent

# Note: comparison_block.py usually has multiple functions.
# Original ComparisonTool called compare_ingredients, compare_prices, compare_benefits, determine_winner, generate_recommendation.
# I will replicate that aggregation logic here.


logger = logging.getLogger("Workers")


class BenefitsWorker(BaseAgent):
    """Extract product benefits"""

    SPECIALIZATIONS = ["extract_benefits", "analyze_ingredients", "benefits"]

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Extracting benefits...")
        try:
            product_dict = context.product_data.model_dump()
            benefits = extract_benefits(product_dict)

            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.benefits = benefits
            return self.create_result(
                AgentStatus.COMPLETE, context, f"Extracted {len(benefits)} benefits"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose_for_task(self, task_type: str, context: AgentContext):
        # Primitive proposal logic to satisfy orchestrator if it still uses proposals
        from ..core.proposals import AgentProposal

        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None


class UsageWorker(BaseAgent):
    """Format usage instructions"""

    SPECIALIZATIONS = ["format_usage", "extract_usage", "usage"]

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Extracting usage instructions...")
        try:
            product_dict = context.product_data.model_dump()
            usage = extract_usage_instructions(product_dict)

            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.usage = usage
            return self.create_result(
                AgentStatus.COMPLETE, context, "Extracted usage instructions"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose_for_task(self, task_type: str, context: AgentContext):
        from ..core.proposals import AgentProposal

        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None


class QuestionsWorker(BaseAgent):
    """Generate FAQ questions"""

    MIN_QUESTIONS = 15  # Assignment requirement
    SPECIALIZATIONS = ["generate_faqs", "create_questions", "questions"]

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Generating questions...")
        try:
            product_dict = context.product_data.model_dump()

            # Use logic block directly
            # Note: generate_questions_by_category logic might need augmentation if it falls short
            # But the user previously updated it to use _augment_with_general_questions
            # We will use that if available, or manual augmentation here.

            # Assuming logic block is up to date with previous edits
            questions = generate_questions_by_category(
                product_dict, min_questions=self.MIN_QUESTIONS
            )

            # Re-verify count just in case
            if len(questions) < self.MIN_QUESTIONS:
                # Attempt to augment manually if logic block didn't cover it (redundancy)
                try:
                    questions = _augment_with_general_questions(
                        questions,
                        self.MIN_QUESTIONS,
                        product_dict.get("name", "Product"),
                    )
                except NameError:
                    pass  # Function might not be imported if I didn't verify it exported

            qa_list = [
                (q, a, c) for q, a, c in questions
            ]  # Ensure it's list of tuples/dicts as expected

            # Convert to list of dicts/tuples compatible with validation?
            # Validation checks context.generated_questions
            context.generated_questions = qa_list

            return self.create_result(
                AgentStatus.COMPLETE, context, f"Generated {len(qa_list)} questions"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose_for_task(self, task_type: str, context: AgentContext):
        from ..core.proposals import AgentProposal

        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None


class ComparisonWorker(BaseAgent):
    """Create product comparison"""

    SPECIALIZATIONS = ["compare_products", "product_comparison", "comparison"]

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Performing comparison...")
        if not context.comparison_data:
            return self.create_result(
                AgentStatus.COMPLETE, context, "Skipped (No data)"
            )

        try:
            product_a = context.product_data.model_dump(exclude_none=True)
            product_b = context.comparison_data.model_dump(exclude_none=True)

            # Aggregated comparison logic
            comparison_results = {
                "ingredients": compare_ingredients(product_a, product_b),
                "price": compare_prices(product_a, product_b),
                "benefits": compare_benefits(product_a, product_b),
                "winners": determine_winner(product_a, product_b),
                "recommendation": generate_recommendation(product_a, product_b),
            }

            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.comparison = comparison_results
            return self.create_result(
                AgentStatus.COMPLETE, context, "Comparison complete"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose_for_task(self, task_type: str, context: AgentContext):
        from ..core.proposals import AgentProposal

        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None


class ValidationWorker(BaseAgent):
    """Validate results"""

    MIN_FAQ_QUESTIONS = 15  # ✅ FIX: Was 10, now 15
    SPECIALIZATIONS = ["validate_results", "quality_check", "validation"]

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Validating results...")

        errors = []
        if not context.product_data or not context.product_data.name:
            errors.append("Missing product name")

        if not context.analysis_results or not context.analysis_results.benefits:
            errors.append("Benefits extraction failed or empty")

        questions = context.generated_questions or []

        if len(questions) < self.MIN_FAQ_QUESTIONS:
            errors.append(
                f"FAQ must have {self.MIN_FAQ_QUESTIONS}+ questions, found {len(questions)}"
            )

        context.validation_errors = errors
        context.is_valid = len(errors) == 0

        if context.is_valid:
            return self.create_result(
                AgentStatus.COMPLETE, context, "Validation passed"
            )
        else:
            return self.create_result(
                AgentStatus.COMPLETE, context, f"Validation failed: {errors}"
            )  # Returning COMPLETE so orchestrator can decide what to do (e.g. retry) or failed?
            # Original returned COMPLETE to allow orchestrator logic to handle 'is_valid' flag.

    def propose_for_task(self, task_type: str, context: AgentContext):
        return None  # Usually called explicitly by orchestrator? Or needs to propose?
        # Orchestrator calls it explicitly at end of loop usually.
