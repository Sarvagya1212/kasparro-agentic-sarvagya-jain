"""
Worker Agents: Specialized units of work.
Each worker is responsible for a specific domain of the analysis/generation process.
"""

import logging
from typing import List, Optional

from .agents import BaseAgent
from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    AnalysisResults,
    TaskDirective,
)
from .tools import ToolRegistry
from .tools.content_tools import create_default_toolbox

logger = logging.getLogger("Workers")


class BaseWorker(BaseAgent):
    """Base class for workers, holding a toolbox."""

    def __init__(
        self,
        name: str,
        role: str = "Worker",
        backstory: str = "Specialized worker",
        toolbox: Optional[ToolRegistry] = None,
    ):
        super().__init__(name, role, backstory)
        self.toolbox = toolbox or create_default_toolbox()


class BenefitsWorker(BaseWorker):
    """Worker dedicated to extracting product benefits."""

    def __init__(self, name: str):
        super().__init__(
            name,
            role="Benefits Specialist",
            backstory="A specialized dermatologist assistant focused on identifying key skincare benefits from technical data.",
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Extracting benefits...")
        try:
            product_dict = context.product_data.model_dump()
            tool = self.toolbox.get("benefits_extractor")
            if not tool:
                return self.create_result(
                    AgentStatus.ERROR, context, "benefits_extractor tool not found"
                )

            result = tool.run(product_data=product_dict)
            benefits = result.data if result.success else []

            # Initialize analysis_results if None
            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.benefits = benefits
            context.log_decision(self.name, f"Extracted {len(benefits)} benefits.")
            return self.create_result(
                AgentStatus.COMPLETE, context, f"Extracted {len(benefits)} benefits"
            )

        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class UsageWorker(BaseWorker):
    """Worker dedicated to extracting usage instructions."""

    def __init__(self, name: str):
        super().__init__(
            name,
            role="Usage Instruction Specialist",
            backstory="Expert in clear, safe, and effective product usage guidelines.",
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Extracting usage instructions...")
        try:
            product_dict = context.product_data.model_dump()
            tool = self.toolbox.get("usage_extractor")
            if not tool:
                return self.create_result(
                    AgentStatus.ERROR, context, "usage_extractor tool not found"
                )

            result = tool.run(product_data=product_dict)
            usage = result.data if result.success else ""

            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.usage = usage
            context.log_decision(self.name, "Extracted usage instructions.")
            return self.create_result(
                AgentStatus.COMPLETE, context, "Extracted usage instructions"
            )

        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class QuestionsWorker(BaseWorker):
    """Worker dedicated to generating FAQ questions."""

    def __init__(self, name: str):
        super().__init__(
            name,
            role="FAQ Generator",
            backstory="Customer success specialist anticipating common user questions and concerns.",
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Generating questions...")
        try:
            product_dict = context.product_data.model_dump()
            tool = self.toolbox.get("faq_generator")
            if not tool:
                return self.create_result(
                    AgentStatus.ERROR, context, "faq_generator tool not found"
                )

            result = tool.run(product_data=product_dict, min_questions=15)
            qa_list = result.data if result.success else []

            context.generated_questions = qa_list
            context.log_decision(self.name, f"Generated {len(qa_list)} questions.")
            return self.create_result(
                AgentStatus.COMPLETE, context, f"Generated {len(qa_list)} questions"
            )

        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class ComparisonWorker(BaseWorker):
    """Worker dedicated to product comparison."""

    def __init__(self, name: str):
        super().__init__(
            name,
            role="Product Analyst",
            backstory="Objective analyst providing fair and data-driven product comparisons.",
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Performing comparison...")
        if not context.comparison_data:
            context.log_decision(self.name, "No comparison data available. Skipping.")
            return self.create_result(
                AgentStatus.COMPLETE, context, "Skipped (No data)"
            )

        try:
            product_dict = context.product_data.model_dump()
            other_dict = context.comparison_data.model_dump()

            tool = self.toolbox.get("product_comparison")
            if not tool:
                return self.create_result(
                    AgentStatus.ERROR, context, "product_comparison tool not found"
                )

            result = tool.run(product_a=product_dict, product_b=other_dict)
            comparison_results = result.data if result.success else {}

            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.comparison = comparison_results
            context.log_decision(self.name, "Completed comparison analysis.")
            return self.create_result(
                AgentStatus.COMPLETE, context, "Comparison complete"
            )

        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class ValidationWorker(BaseAgent):
    """
    Worker responsible for validating the aggregated results.
    Reports pass/fail back to Delegator.
    """

    MIN_FAQ_QUESTIONS = 15

    def __init__(self, name: str):
        super().__init__(
            name,
            role="Quality Assurance Officer",
            backstory="Strict auditor ensuring all content meets high-quality standards before release.",
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Validating results...")

        errors = []

        # 1. Product Name
        if not context.product_data or not context.product_data.name:
            errors.append("Missing product name")

        # 2. Key Ingredients
        if not context.product_data or not context.product_data.key_ingredients:
            errors.append("Missing key ingredients")

        # 3. Benefits
        if not context.analysis_results or not context.analysis_results.benefits:
            errors.append("Benefits extraction failed or empty")

        # 4. FAQ Count
        faq_count = (
            len(context.generated_questions) if context.generated_questions else 0
        )
        if faq_count < self.MIN_FAQ_QUESTIONS:
            errors.append(
                f"Insufficient FAQ questions: {faq_count} < {self.MIN_FAQ_QUESTIONS}"
            )

        context.validation_errors = errors
        context.is_valid = len(errors) == 0

        if context.is_valid:
            context.log_decision(self.name, "PASS: All validation checks passed")
            return self.create_result(
                AgentStatus.COMPLETE, context, "Validation passed"
            )
        else:
            context.log_decision(self.name, f"FAIL: {', '.join(errors)}")
            # Return ERROR or a specific status to indicate validation failure?
            # In CWD, the Delegator will read context.is_valid.
            # But returning COMPLETE with is_valid=False allows Delegator to inspect it.
            return self.create_result(
                AgentStatus.COMPLETE, context, "Validation completed (Found errors)"
            )
