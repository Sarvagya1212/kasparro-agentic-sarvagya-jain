"""All worker agents - using can_handle() for simple routing."""

import logging
from typing import Optional

from ..core.models import (
    GlobalContext,
    AgentResult,
    AgentStatus,
    ProcessingStage,
    TaskDirective,
)
from ..core.proposals import Rejection

from ..logic_blocks.comparison_block import (
    compare_benefits,
    compare_ingredients,
    compare_prices,
    determine_winner,
    generate_recommendation,
)
from ..logic_blocks.question_generator import generate_questions_by_category
from ..logic_blocks.usage_block import extract_usage_instructions

logger = logging.getLogger("Workers")


class UsageWorker:
    """Extract usage instructions - activates at INGEST stage."""
    
    def __init__(self, name: str = "UsageWorker"):
        self.name = name

    def can_handle(self, state: GlobalContext) -> bool:
        """Can handle if at INGEST and usage not extracted."""
        return (
            state.stage == ProcessingStage.INGEST and
            state.product_input is not None and
            not state.generated_content.usage
        )

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Extracting usage...")
        try:
            product_dict = context.product_input.model_dump()
            usage = extract_usage_instructions(product_dict)
            
            context.generated_content.usage = usage
            context.advance_stage(ProcessingStage.SYNTHESIS)
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETE,
                context=context,
                message="Extracted usage"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                context=context,
                message=str(e)
            )


class QuestionsWorker:
    """Generate FAQ questions - activates at SYNTHESIS stage."""
    FAQ_BUFFER = 20  # Request more than needed
    MIN_REQUIRED = 15

    def __init__(self, name: str = "QuestionsWorker"):
        self.name = name

    def can_handle(self, state: GlobalContext) -> bool:
        """Can handle if at SYNTHESIS and questions not generated."""
        return (
            state.stage == ProcessingStage.SYNTHESIS and
            state.product_input is not None and
            len(state.generated_content.faq_questions) < self.MIN_REQUIRED
        )

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Generating {self.FAQ_BUFFER} questions...")
        try:
            product_dict = context.product_input.model_dump()
            questions = generate_questions_by_category(product_dict, min_questions=self.FAQ_BUFFER)
            
            context.generated_content.faq_questions = questions
            context.advance_stage(ProcessingStage.DRAFTING)
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETE,
                context=context,
                message=f"Generated {len(questions)} questions"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                context=context,
                message=str(e)
            )


class ComparisonWorker:
    """Create product comparison - activates at DRAFTING stage."""
    
    def __init__(self, name: str = "ComparisonWorker"):
        self.name = name

    def can_handle(self, state: GlobalContext) -> bool:
        """Can handle if at DRAFTING and comparison not done."""
        return (
            state.stage == ProcessingStage.DRAFTING and
            state.comparison_input is not None and
            not state.generated_content.comparison
        )

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Comparing products...")
        
        if not context.comparison_input:
            context.advance_stage(ProcessingStage.VERIFICATION)
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETE,
                context=context,
                message="Skipped (no comparison data)"
            )

        try:
            product_a = context.product_input.model_dump(exclude_none=True)
            product_b = context.comparison_input.model_dump(exclude_none=True)

            comparison_results = {
                "ingredients": compare_ingredients(product_a, product_b),
                "price": compare_prices(product_a, product_b),
                "benefits": compare_benefits(product_a, product_b),
                "winner": determine_winner(product_a, product_b),
                "recommendation": generate_recommendation(product_a, product_b),
            }

            context.generated_content.comparison = comparison_results
            context.advance_stage(ProcessingStage.VERIFICATION)
            
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETE,
                context=context,
                message="Comparison complete"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                context=context,
                message=str(e)
            )


class ValidationWorker:
    """Validate results - activates at VERIFICATION stage."""
    MIN_FAQ_THRESHOLD = 15  # Critical requirement

    def __init__(self, name: str = "ValidationWorker"):
        self.name = name

    def can_handle(self, state: GlobalContext) -> bool:
        """Can handle if at VERIFICATION stage."""
        return (
            state.stage == ProcessingStage.VERIFICATION and
            not state.is_valid
        )

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Validating (threshold={self.MIN_FAQ_THRESHOLD})...")

        errors = []
        
        # Check product
        if not context.product_input or not context.product_input.name:
            errors.append("Missing product name")

        # Check FAQ count
        faq_count = len(context.generated_content.faq_questions)
        if faq_count < self.MIN_FAQ_THRESHOLD:
            errors.append(f"FAQ count {faq_count} < {self.MIN_FAQ_THRESHOLD}")
            
            # Return Rejection to trigger re-run
            context.errors = errors
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.VALIDATION_FAILED,
                context=context,
                message=f"Rejection: Need {self.MIN_FAQ_THRESHOLD} FAQs, got {faq_count}"
            )

        # All checks passed
        context.errors = []
        context.is_valid = True
        context.advance_stage(ProcessingStage.COMPLETE)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETE,
            context=context,
            message=f"Validation passed ({faq_count} FAQs)"
        )
