"""
Agent Implementations with True Autonomy.
Each agent can propose actions based on context assessment.
Agents decide when they can help, not the orchestrator.
"""

import logging
from typing import Dict, List, Optional

from .agents import BaseAgent
from .data.products import GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT
from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    AnalysisResults,
    ProductData,
    TaskDirective,
)
from .proposals import AgentProposal
from .templates.comparison_template import ComparisonTemplate
from .templates.faq_template import FAQTemplate
from .templates.product_page_template import ProductPageTemplate
from .tools import ToolRegistry
from .tools.content_tools import create_default_toolbox

logger = logging.getLogger("Agents")


class DataAgent(BaseAgent):
    """
    Responsible for fetching and loading product data.
    Proposes action when no product data exists.
    """

    def __init__(self, name: str = "DataAgent"):
        super().__init__(
            name=name,
            role="Data Loader",
            backstory="Specialist in loading and validating product data."
        )

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if no product data loaded."""
        return context.product_data is None

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to load data if none exists."""
        if not self.can_handle(context):
            return AgentProposal(
                agent_name=self.name,
                action="load_data",
                confidence=0.0,
                reason="Product data already loaded",
                preconditions_met=False
            )

        return AgentProposal(
            agent_name=self.name,
            action="load_data",
            confidence=0.95,
            reason="No product data loaded - I can fetch and validate it",
            preconditions_met=True,
            priority=10  # High priority - must happen first
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Loading product data...")

        try:
            raw_data = GLOWBOOST_PRODUCT.copy()
            raw_comp = RADIANCE_PLUS_PRODUCT.copy()

            if "how_to_use" in raw_data:
                raw_data["usage_instructions"] = raw_data.pop("how_to_use")
            if "how_to_use" in raw_comp:
                raw_comp["usage_instructions"] = raw_comp.pop("how_to_use")

            context.product_data = ProductData(**raw_data)
            context.comparison_data = ProductData(**raw_comp)

            context.analysis_results = None
            context.generated_questions = []
            context.is_valid = False
            context.validation_errors = []

            return self.create_result(
                AgentStatus.CONTINUE, context, "Data loaded and schema validated"
            )

        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            return self.create_result(
                AgentStatus.ERROR, context, f"Schema mismatch: {str(e)}"
            )


class SyntheticDataAgent(BaseAgent):
    """
    Generates synthetic competitor data when comparison_data is missing.
    Proposes action when product data exists but no comparison.
    """

    def __init__(self, name: str = "SyntheticDataAgent"):
        super().__init__(
            name=name,
            role="Synthetic Data Generator",
            backstory="Creates contrasting competitor products for comparisons."
        )

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if product exists but no comparison."""
        return context.product_data is not None and context.comparison_data is None

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to generate synthetic data if needed."""
        if context.product_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="generate_synthetic",
                confidence=0.0,
                reason="Need product data first",
                preconditions_met=False
            )

        if context.comparison_data is not None:
            return AgentProposal(
                agent_name=self.name,
                action="generate_synthetic",
                confidence=0.0,
                reason="Comparison data already exists",
                preconditions_met=False
            )

        return AgentProposal(
            agent_name=self.name,
            action="generate_synthetic",
            confidence=0.90,
            reason="Product data exists but no comparison - I can generate Product B",
            preconditions_met=True,
            priority=9
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Generating synthetic competitor...")

        if context.comparison_data:
            context.log_decision(self.name, "Comparison data already exists. Skipping.")
            return self.create_result(
                AgentStatus.CONTINUE, context, "Comparison data exists"
            )

        try:
            synthetic_product = {
                "name": "PureGlow Retinol Night Serum",
                "brand": "PureGlow",
                "concentration": "0.5% Retinol + 2% Bakuchiol",
                "key_ingredients": ["Retinol", "Bakuchiol", "Squalane", "Ceramides"],
                "benefits": ["Anti-aging", "Wrinkle reduction", "Cell renewal"],
                "price": 850.0,
                "currency": "INR",
                "size": "30ml",
                "skin_types": ["Mature", "Dry", "Normal"],
                "side_effects": "May cause initial purging",
                "usage_instructions": "Apply 2-3 drops at night only.",
            }

            context.comparison_data = ProductData(**synthetic_product)
            context.log_decision(
                self.name,
                f"Generated competitor: {synthetic_product['name']} @ ₹{synthetic_product['price']}"
            )

            return self.create_result(
                AgentStatus.CONTINUE, context, "Synthetic competitor generated"
            )

        except Exception as e:
            logger.error(f"Synthetic data generation failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class AnalysisAgent(BaseAgent):
    """
    Transforms raw data into insights using tools.
    Proposes action when data exists but analysis not done.
    """

    def __init__(self, name: str = "AnalysisAgent", toolbox: Optional[ToolRegistry] = None):
        super().__init__(
            name=name,
            role="Data Analyst",
            backstory="Expert at extracting benefits and generating insights."
        )
        self.toolbox = toolbox or create_default_toolbox()

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if product data exists but no analysis."""
        return (
            context.product_data is not None and
            context.analysis_results is None
        )

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to analyze if data ready but no analysis."""
        if context.product_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="analyze",
                confidence=0.0,
                reason="Need product data first",
                preconditions_met=False
            )

        if context.analysis_results is not None:
            return AgentProposal(
                agent_name=self.name,
                action="analyze",
                confidence=0.0,
                reason="Analysis already complete",
                preconditions_met=False
            )

        return AgentProposal(
            agent_name=self.name,
            action="analyze",
            confidence=0.85,
            reason="Product data ready - I can extract benefits and generate FAQs",
            preconditions_met=True,
            priority=8
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not context.product_data:
            return self.create_result(AgentStatus.RETRY, context, "Missing product data")

        logger.info(f"{self.name}: Analyzing product data...")

        try:
            product_dict = context.product_data.model_dump()
            other_dict = context.comparison_data.model_dump() if context.comparison_data else None

            # Autonomous tool selection
            benefits = []
            benefits_tool = self.toolbox.get("benefits_extractor")
            if benefits_tool:
                context.log_decision(self.name, "Selected 'benefits_extractor' tool")
                result = benefits_tool.run(product_data=product_dict)
                benefits = result.data if result.success else []

            usage = ""
            usage_tool = self.toolbox.get("usage_extractor")
            if usage_tool:
                context.log_decision(self.name, "Selected 'usage_extractor' tool")
                result = usage_tool.run(product_data=product_dict)
                usage = result.data if result.success else ""

            qa_list = []
            faq_tool = self.toolbox.get("faq_generator")
            if faq_tool:
                context.log_decision(self.name, "Selected 'faq_generator' tool")
                result = faq_tool.run(product_data=product_dict, min_questions=15)
                qa_list = result.data if result.success else []

            comparison_results: Dict = {}
            if other_dict:
                comp_tool = self.toolbox.get("product_comparison")
                if comp_tool:
                    context.log_decision(self.name, "Selected 'product_comparison' tool")
                    result = comp_tool.run(product_a=product_dict, product_b=other_dict)
                    comparison_results = result.data if result.success else {}

            context.analysis_results = AnalysisResults(
                benefits=benefits, usage=usage, comparison=comparison_results
            )
            context.generated_questions = qa_list

            return self.create_result(
                AgentStatus.CONTINUE, context, "Analysis complete"
            )

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class ValidationAgent(BaseAgent):
    """
    Validates analysis results before generation.
    Proposes action when analysis exists but not validated.
    """

    MIN_FAQ_QUESTIONS = 15

    def __init__(self, name: str = "ValidationAgent"):
        super().__init__(
            name=name,
            role="Quality Assurance",
            backstory="Strict auditor ensuring content meets standards."
        )

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if analysis done but not validated."""
        return (
            context.analysis_results is not None and
            not context.is_valid
        )

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to validate if analysis ready."""
        if context.analysis_results is None:
            return AgentProposal(
                agent_name=self.name,
                action="validate",
                confidence=0.0,
                reason="Need analysis results first",
                preconditions_met=False
            )

        if context.is_valid:
            return AgentProposal(
                agent_name=self.name,
                action="validate",
                confidence=0.0,
                reason="Already validated",
                preconditions_met=False
            )

        return AgentProposal(
            agent_name=self.name,
            action="validate",
            confidence=0.88,
            reason="Analysis complete - I can validate quality before generation",
            preconditions_met=True,
            priority=7
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info(f"{self.name}: Validating results...")

        errors: List[str] = []
        needs_retry = False

        if not context.product_data or not context.product_data.name:
            errors.append("Missing product name")
            context.log_decision(self.name, "FAIL: Product name missing")

        if not context.product_data or not context.product_data.key_ingredients:
            errors.append("Missing key ingredients")
            context.log_decision(self.name, "FAIL: key_ingredients empty")
            needs_retry = True

        if not context.analysis_results or not context.analysis_results.benefits:
            errors.append("Benefits extraction failed")
            context.log_decision(self.name, "FAIL: Benefits empty")
            needs_retry = True

        faq_count = len(context.generated_questions) if context.generated_questions else 0
        if faq_count < self.MIN_FAQ_QUESTIONS:
            errors.append(f"Insufficient FAQs: {faq_count} < {self.MIN_FAQ_QUESTIONS}")
            context.log_decision(self.name, f"FAIL: FAQ count {faq_count}/{self.MIN_FAQ_QUESTIONS}")
            needs_retry = True
        else:
            context.log_decision(self.name, f"PASS: FAQ count {faq_count}")

        context.validation_errors = errors
        context.is_valid = len(errors) == 0

        if context.is_valid:
            context.log_decision(self.name, "PASS: All validation checks passed")
            return self.create_result(AgentStatus.CONTINUE, context, "Validation passed")
        elif needs_retry:
            return self.create_result(AgentStatus.RETRY, context, f"Retry: {', '.join(errors)}")
        else:
            return self.create_result(AgentStatus.VALIDATION_FAILED, context, f"Failed: {', '.join(errors)}")


class GenerationAgent(BaseAgent):
    """
    Renders templates and saves files.
    Proposes action when validated but not generated.
    """

    def __init__(self, name: str = "GenerationAgent"):
        super().__init__(
            name=name,
            role="Content Generator",
            backstory="Expert at rendering templates into final content."
        )
        self._generated = False

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if validated but not generated."""
        return context.is_valid and not self._generated

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to generate if validated."""
        if not context.is_valid:
            return AgentProposal(
                agent_name=self.name,
                action="generate",
                confidence=0.0,
                reason="Need validation first",
                preconditions_met=False
            )

        if self._generated:
            return AgentProposal(
                agent_name=self.name,
                action="generate",
                confidence=0.0,
                reason="Already generated",
                preconditions_met=False
            )

        return AgentProposal(
            agent_name=self.name,
            action="generate",
            confidence=0.92,
            reason="Validation passed - I can generate all content pages",
            preconditions_met=True,
            priority=6
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not context.is_valid:
            return self.create_result(AgentStatus.ERROR, context, "Context invalid")

        logger.info(f"{self.name}: Generating content...")

        try:
            import json
            from datetime import datetime
            from pathlib import Path

            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            product = context.product_data.model_dump()
            analysis = context.analysis_results.model_dump()
            outputs_generated = []

            # FAQ Page
            if context.generated_questions:
                context.log_decision(self.name, "Generating FAQ page")
                faq_data = {
                    "product_name": product["name"],
                    "qa_pairs": [(q, a) for q, a, c in context.generated_questions],
                    "categories": {},
                    "timestamp": datetime.now().isoformat(),
                }
                for i, (q, a, category) in enumerate(context.generated_questions):
                    if category not in faq_data["categories"]:
                        faq_data["categories"][category] = []
                    faq_data["categories"][category].append(i)

                faq_template = FAQTemplate()
                faq_output = faq_template.render(faq_data)
                with open(output_dir / "faq.json", "w", encoding="utf-8") as f:
                    json.dump(faq_output, f, indent=2, ensure_ascii=False)
                outputs_generated.append("faq.json")

            # Product Page
            if product:
                context.log_decision(self.name, "Generating Product page")
                product_page_data = {
                    "name": product["name"],
                    "brand": product.get("brand", ""),
                    "concentration": product.get("concentration", ""),
                    "benefits": analysis["benefits"],
                    "ingredients": product.get("key_ingredients", []),
                    "usage_instructions": analysis["usage"],
                    "price": product.get("price", 0),
                    "currency": product.get("currency", "INR"),
                    "size": product.get("size", ""),
                    "skin_types": product.get("skin_types", []),
                    "side_effects": product.get("side_effects", "None"),
                }
                product_template = ProductPageTemplate()
                prod_output = product_template.render(product_page_data)
                with open(output_dir / "product_page.json", "w", encoding="utf-8") as f:
                    json.dump(prod_output, f, indent=2, ensure_ascii=False)
                outputs_generated.append("product_page.json")

            # Comparison Page
            if context.comparison_data and analysis.get("comparison"):
                context.log_decision(self.name, "Generating Comparison page")
                comp = analysis["comparison"]
                product_b = context.comparison_data.model_dump()

                differences = [
                    {
                        "aspect": "Ingredients",
                        "details": f"Common: {', '.join(comp['ingredients']['common_ingredients'])}."
                    },
                    {
                        "aspect": "Price",
                        "details": f"₹{comp['price']['difference']} difference."
                    },
                ]

                comp_data = {
                    "primary": product,
                    "other": product_b,
                    "differences": differences,
                    "recommendation": comp["recommendation"],
                    "winner_categories": comp["winners"],
                }

                comp_template = ComparisonTemplate()
                comp_output = comp_template.render(comp_data)
                with open(output_dir / "comparison_page.json", "w", encoding="utf-8") as f:
                    json.dump(comp_output, f, indent=2, ensure_ascii=False)
                outputs_generated.append("comparison_page.json")

            self._generated = True
            return self.create_result(
                AgentStatus.COMPLETE,
                context,
                f"Generated: {', '.join(outputs_generated)}"
            )

        except Exception as e:
            logger.exception("Generation failed")
            return self.create_result(AgentStatus.ERROR, context, str(e))
