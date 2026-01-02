"""All worker agents - using GlobalContext (Blackboard pattern)"""

import logging
from typing import Any, Dict, List, Optional

from ..core.models import (
    GlobalContext,
    AgentResult,
    AgentStatus,
    ProcessingStage,
    TaskDirective,
)
from ..core.proposals import AgentProposal

# Import Logic Blocks
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
    """Extract and format usage instructions."""
    
    def __init__(self, name: str = "UsageWorker"):
        self.name = name

    def create_result(self, status: AgentStatus, context: GlobalContext, message: str) -> AgentResult:
        return AgentResult(agent_name=self.name, status=status, context=context, message=message)

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Extracting usage...")
        try:
            product_dict = context.product_input.model_dump()
            usage = extract_usage_instructions(product_dict)
            
            context.generated_content.usage = usage
            context.advance_stage(ProcessingStage.SYNTHESIS)
            
            return self.create_result(AgentStatus.COMPLETE, context, f"Extracted usage")
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose(self, context: GlobalContext) -> AgentProposal:
        should_act = (
            context.product_input is not None and
            not context.generated_content.usage
        )
        
        return AgentProposal(
            agent_name=self.name,
            action="extract_usage",
            confidence=0.85 if should_act else 0.0,
            reason="Ready to extract usage." if should_act else "Usage already extracted.",
            preconditions_met=should_act,
            priority=5
        )


class QuestionsWorker:
    """Generate FAQ questions using LLM."""
    MIN_QUESTIONS = 15

    def __init__(self, name: str = "QuestionsWorker"):
        self.name = name

    def create_result(self, status: AgentStatus, context: GlobalContext, message: str) -> AgentResult:
        return AgentResult(agent_name=self.name, status=status, context=context, message=message)

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Generating questions...")
        try:
            product_dict = context.product_input.model_dump()
            questions = generate_questions_by_category(product_dict, min_questions=self.MIN_QUESTIONS)
            
            context.generated_content.faq_questions = questions
            context.advance_stage(ProcessingStage.DRAFTING)
            
            return self.create_result(AgentStatus.COMPLETE, context, f"Generated {len(questions)} questions")
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose(self, context: GlobalContext) -> AgentProposal:
        should_act = (
            context.product_input is not None and
            len(context.generated_content.faq_questions) < self.MIN_QUESTIONS
        )

        return AgentProposal(
            agent_name=self.name,
            action="generate_faqs",
            confidence=0.80 if should_act else 0.0,
            reason="Ready to generate questions." if should_act else "Questions done.",
            preconditions_met=should_act,
            priority=6
        )


class ComparisonWorker:
    """Create product comparison using LLM."""
    
    def __init__(self, name: str = "ComparisonWorker"):
        self.name = name

    def create_result(self, status: AgentStatus, context: GlobalContext, message: str) -> AgentResult:
        return AgentResult(agent_name=self.name, status=status, context=context, message=message)

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Performing comparison...")
        
        if not context.comparison_input:
            return self.create_result(AgentStatus.COMPLETE, context, "Skipped (No comparison data)")

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
            
            return self.create_result(AgentStatus.COMPLETE, context, "Comparison complete")
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))

    def propose(self, context: GlobalContext) -> AgentProposal:
        should_act = (
            context.product_input is not None and
            context.comparison_input is not None and
            not context.generated_content.comparison
        )

        return AgentProposal(
            agent_name=self.name,
            action="compare_products",
            confidence=0.82 if should_act else 0.0,
            reason="Ready to compare." if should_act else "Comparison done or no data.",
            preconditions_met=should_act,
            priority=5
        )


class ValidationWorker:
    """Validate all generated content meets requirements."""
    MIN_FAQ_QUESTIONS = 15

    def __init__(self, name: str = "ValidationWorker"):
        self.name = name

    def create_result(self, status: AgentStatus, context: GlobalContext, message: str) -> AgentResult:
        return AgentResult(agent_name=self.name, status=status, context=context, message=message)

    def run(self, context: GlobalContext, directive: Optional[TaskDirective] = None) -> AgentResult:
        logger.info(f"{self.name}: Validating...")

        errors = []
        
        if not context.product_input or not context.product_input.name:
            errors.append("Missing product name")

        if len(context.generated_content.faq_questions) < self.MIN_FAQ_QUESTIONS:
            errors.append(
                f"FAQ must have {self.MIN_FAQ_QUESTIONS}+ questions, "
                f"found {len(context.generated_content.faq_questions)}"
            )

        context.errors = errors
        context.is_valid = len(errors) == 0
        
        if context.is_valid:
            context.advance_stage(ProcessingStage.COMPLETE)

        if context.is_valid:
            return self.create_result(AgentStatus.COMPLETE, context, "Validation passed")
        else:
            return self.create_result(AgentStatus.VALIDATION_FAILED, context, f"Failed: {errors}")

    def propose(self, context: GlobalContext) -> AgentProposal:
        is_ready = len(context.generated_content.faq_questions) >= self.MIN_FAQ_QUESTIONS
        should_act = is_ready and not context.is_valid

        return AgentProposal(
            agent_name=self.name,
            action="validate_results",
            confidence=0.95 if should_act else 0.0,
            reason="Ready to validate." if should_act else "Not ready or already valid.",
            preconditions_met=should_act,
            priority=9
        )
