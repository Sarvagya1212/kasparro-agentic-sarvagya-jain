"""
Agent Implementations with True Autonomy.
Each agent can propose actions based on context assessment.
Agents decide when they can help, not the orchestrator.
"""

import logging
from typing import Dict, List, Optional

from skincare_agent_system.actors.agents import BaseAgent
from skincare_agent_system.core.context_analyzer import get_context_analyzer
from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    AnalysisResults,
    ProductData,
    TaskDirective,
)
from skincare_agent_system.core.proposals import AgentProposal
from skincare_agent_system.data.products import GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT
from skincare_agent_system.templates.comparison_template import ComparisonTemplate
from skincare_agent_system.templates.faq_template import FAQTemplate
from skincare_agent_system.templates.product_page_template import ProductPageTemplate

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
            backstory="Specialist in loading and validating product data.",
        )

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if no product data loaded."""
        return context.product_data is None

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to load data if none exists - DYNAMIC scoring."""
        analyzer = get_context_analyzer()

        if not self.can_handle(context):
            return AgentProposal(
                agent_name=self.name,
                action="load_data",
                confidence=0.0,
                reason="Product data already loaded",
                preconditions_met=False,
            )

        # Calculate dynamic confidence and priority
        base_confidence = analyzer.assess_data_readiness(context)
        bonus = analyzer.get_context_bonus(self.name, context)
        confidence = min(1.0, max(0.0, base_confidence + bonus))
        priority = analyzer.get_base_priority(self.name, context)

        return AgentProposal(
            agent_name=self.name,
            action="load_data",
            confidence=confidence,
            reason=f"No product data loaded - I can fetch and validate it (conf: {confidence:.2f})",
            preconditions_met=True,
            priority=priority,
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
            backstory="Creates contrasting competitor products for comparisons.",
        )

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if product exists but no comparison."""
        return context.product_data is not None and context.comparison_data is None

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to generate synthetic data if needed - DYNAMIC scoring."""
        analyzer = get_context_analyzer()

        if context.product_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="generate_synthetic",
                confidence=0.0,
                reason="Need product data first",
                preconditions_met=False,
            )

        if context.comparison_data is not None:
            return AgentProposal(
                agent_name=self.name,
                action="generate_synthetic",
                confidence=0.0,
                reason="Comparison data already exists",
                preconditions_met=False,
            )

        # Calculate dynamic confidence and priority
        base_confidence = 0.85  # High base for ready context
        bonus = analyzer.get_context_bonus(self.name, context)
        confidence = min(1.0, max(0.0, base_confidence + bonus))
        priority = analyzer.get_base_priority(self.name, context)

        return AgentProposal(
            agent_name=self.name,
            action="generate_synthetic",
            confidence=confidence,
            reason=f"Product data exists but no comparison - I can generate Product B (conf: {confidence:.2f})",
            preconditions_met=True,
            priority=priority,
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
                f"Generated competitor: {synthetic_product['name']} @ ₹{synthetic_product['price']}",
            )

            return self.create_result(
                AgentStatus.CONTINUE, context, "Synthetic competitor generated"
            )

        except Exception as e:
            logger.error(f"Synthetic data generation failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class GenerationAgent(BaseAgent):
    """
    Renders templates and saves files.
    Proposes action when validated but not generated.
    """

    def __init__(self, name: str = "GenerationAgent"):
        super().__init__(
            name=name,
            role="Content Generator",
            backstory="Expert at rendering templates into final content.",
        )
        self._generated = False

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if validated but not generated."""
        return context.is_valid and not self._generated

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to generate if validated - DYNAMIC scoring."""
        analyzer = get_context_analyzer()

        if not context.is_valid:
            return AgentProposal(
                agent_name=self.name,
                action="generate",
                confidence=0.0,
                reason="Need validation first",
                preconditions_met=False,
            )

        if self._generated:
            return AgentProposal(
                agent_name=self.name,
                action="generate",
                confidence=0.0,
                reason="Already generated",
                preconditions_met=False,
            )

        # Calculate dynamic confidence and priority
        base_confidence = analyzer.assess_generation_readiness(context)
        bonus = analyzer.get_context_bonus(self.name, context)
        confidence = min(1.0, max(0.0, base_confidence + bonus))
        priority = analyzer.get_base_priority(self.name, context)

        return AgentProposal(
            agent_name=self.name,
            action="generate",
            confidence=confidence,
            reason=f"Validation passed - I can generate all content pages (conf: {confidence:.2f})",
            preconditions_met=True,
            priority=priority,
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
                        "details": f"Common: {', '.join(comp['ingredients']['common_ingredients'])}.",
                    },
                    {
                        "aspect": "Price",
                        "details": f"₹{comp['price']['difference']} difference.",
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
                with open(
                    output_dir / "comparison_page.json", "w", encoding="utf-8"
                ) as f:
                    json.dump(comp_output, f, indent=2, ensure_ascii=False)
                outputs_generated.append("comparison_page.json")

            self._generated = True
            return self.create_result(
                AgentStatus.COMPLETE,
                context,
                f"Generated: {', '.join(outputs_generated)}",
            )

        except Exception as e:
            logger.exception("Generation failed")
            return self.create_result(AgentStatus.ERROR, context, str(e))
