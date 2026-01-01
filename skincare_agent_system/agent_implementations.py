"""
Agent Implementations using Tool-Based Autonomy.
Agents receive a ToolRegistry and decide which tools to call based on their goal.
This follows the "Separating Tools from Logic" best practice.
"""

import logging
from typing import Dict, List, Optional

from .agents import BaseAgent

# Import existing data sources
from .data.products import GLOWBOOST_PRODUCT, RADIANCE_PLUS_PRODUCT
from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    AnalysisResults,
    ProductData,
    TaskDirective,
)
from .templates.comparison_template import ComparisonTemplate

# Import templates (these could also become tools in a full refactor)
from .templates.faq_template import FAQTemplate
from .templates.product_page_template import ProductPageTemplate
from .tools import ToolRegistry
from .tools.content_tools import create_default_toolbox

logger = logging.getLogger("Agents")


class DataAgent(BaseAgent):
    """
    Responsible for fetching and loading product data.
    Validates raw data into ProductData model.
    """

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info("Fetching product data...")

        try:
            raw_data = GLOWBOOST_PRODUCT.copy()
            raw_comp = RADIANCE_PLUS_PRODUCT.copy()

            # Map fields to match ProductData schema
            if "how_to_use" in raw_data:
                raw_data["usage_instructions"] = raw_data.pop("how_to_use")
            if "how_to_use" in raw_comp:
                raw_comp["usage_instructions"] = raw_comp.pop("how_to_use")

            # Create Typed Objects
            context.product_data = ProductData(**raw_data)
            context.comparison_data = ProductData(**raw_comp)

            # Clear downstream artifacts
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
    Creates a contrasting product for meaningful comparison.
    """

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info("SyntheticDataAgent: Generating synthetic competitor...")

        if context.comparison_data:
            context.log_decision(
                "SyntheticDataAgent", "Comparison data already exists. Skipping."
            )
            return self.create_result(
                AgentStatus.CONTINUE, context, "Comparison data exists"
            )

        try:
            # Generate competitor with CONTRASTING attributes
            synthetic_product = {
                "name": "PureGlow Retinol Night Serum",
                "brand": "PureGlow",
                "concentration": "0.5% Retinol + 2% Bakuchiol",
                "key_ingredients": ["Retinol", "Bakuchiol", "Squalane", "Ceramides"],
                "benefits": [
                    "Anti-aging",
                    "Wrinkle reduction",
                    "Cell renewal",
                    "Overnight repair",
                ],
                "price": 850.0,
                "currency": "INR",
                "size": "30ml",
                "skin_types": ["Mature", "Dry", "Normal"],
                "side_effects": "May cause initial purging; avoid with Vitamin C",
                "usage_instructions": "Apply 2-3 drops at night only. Use SPF next morning.",
            }

            context.comparison_data = ProductData(**synthetic_product)
            price_str = (
                f"₹{context.product_data.price}" if context.product_data else "N/A"
            )
            context.log_decision(
                "SyntheticDataAgent",
                f"Generated contrasting competitor: {synthetic_product['name']} "
                f"@ ₹{synthetic_product['price']} (vs primary @ {price_str})",
            )

            return self.create_result(
                AgentStatus.CONTINUE, context, "Synthetic competitor generated"
            )

        except Exception as e:
            logger.error(f"Synthetic data generation failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class AnalysisAgent(BaseAgent):
    """
    Responsible for transforming raw data into insights.
    Uses tools autonomously based on the goal: "Complete Analysis".
    """

    def __init__(self, name: str, toolbox: Optional[ToolRegistry] = None):
        super().__init__(name)
        self.toolbox = toolbox or create_default_toolbox()

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not context.product_data:
            return self.create_result(
                AgentStatus.RETRY, context, "Missing product data"
            )

        logger.info(
            "AnalysisAgent: Determining which tools to use for goal 'Complete Analysis'..."
        )

        try:
            product_dict = context.product_data.model_dump()

            # --- Ambiguity Handling / Reasoning Step ---
            if (
                product_dict.get("side_effects")
                and "se..." in product_dict["side_effects"]
            ):
                original_text = product_dict["side_effects"]
                reasoned_fix = original_text.replace("se...", "sensitive skin")
                product_dict["side_effects"] = reasoned_fix
                context.product_data.side_effects = reasoned_fix
                context.log_decision(
                    "AnalysisAgent",
                    f"Detected truncation. Inferred and repaired to: '{reasoned_fix}'",
                )

            other_dict = (
                context.comparison_data.model_dump()
                if context.comparison_data
                else None
            )

            # --- AUTONOMOUS TOOL SELECTION ---
            # Goal: Complete Analysis. Agent decides which tools are needed.

            # 1. Benefits extraction
            benefits_tool = self.toolbox.get("benefits_extractor")
            if benefits_tool:
                context.log_decision(
                    "AnalysisAgent",
                    "Selected 'benefits_extractor' tool for benefits analysis",
                )
                benefits_result = benefits_tool.run(product_data=product_dict)
                benefits = benefits_result.data if benefits_result.success else []
            else:
                benefits = []

            # 2. Usage extraction
            usage_tool = self.toolbox.get("usage_extractor")
            if usage_tool:
                context.log_decision(
                    "AnalysisAgent",
                    "Selected 'usage_extractor' tool for usage instructions",
                )
                usage_result = usage_tool.run(product_data=product_dict)
                usage = usage_result.data if usage_result.success else ""
            else:
                usage = ""

            # 3. FAQ generation
            faq_tool = self.toolbox.get("faq_generator")
            if faq_tool:
                context.log_decision(
                    "AnalysisAgent", "Selected 'faq_generator' tool for Q&A generation"
                )
                faq_result = faq_tool.run(product_data=product_dict, min_questions=15)
                qa_list = faq_result.data if faq_result.success else []
            else:
                qa_list = []

            # 4. Comparison (if applicable)
            comparison_results: Dict = {}
            if other_dict:
                comp_tool = self.toolbox.get("product_comparison")
                if comp_tool:
                    context.log_decision(
                        "AnalysisAgent",
                        "Selected 'product_comparison' tool for comparison analysis",
                    )
                    comp_result = comp_tool.run(
                        product_a=product_dict, product_b=other_dict
                    )
                    comparison_results = comp_result.data if comp_result.success else {}

            # Store results
            context.analysis_results = AnalysisResults(
                benefits=benefits, usage=usage, comparison=comparison_results
            )
            context.generated_questions = qa_list

            return self.create_result(
                AgentStatus.CONTINUE, context, "Analysis complete using tools"
            )

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))


class ValidationAgent(BaseAgent):
    """
    Responsible for checking if we have enough info to generate output.
    Acts as a "Gatekeeper" - returns RETRY if requirements not met.
    Logs detailed audit trail for each validation decision.
    """

    MIN_FAQ_QUESTIONS = 15  # Requirement: At least 15 FAQ questions

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        logger.info("Validating analysis results...")

        errors: List[str] = []
        needs_retry = False

        # --- DETAILED VALIDATION WITH AUDIT TRAIL ---

        # 1. Product Name
        if not context.product_data or not context.product_data.name:
            errors.append("Missing product name")
            context.log_decision("ValidationAgent", "FAIL: Product name is missing")

        # 2. Key Ingredients
        if not context.product_data or not context.product_data.key_ingredients:
            errors.append("Missing key ingredients")
            context.log_decision(
                "ValidationAgent", "FAIL: key_ingredients field is empty"
            )
            needs_retry = True

        # 3. Skin Types (important for targeting)
        if not context.product_data or not context.product_data.skin_types:
            errors.append("Missing skin types")
            context.log_decision(
                "ValidationAgent",
                "FAIL: Skin Type was missing - cannot target audience properly",
            )
            needs_retry = True

        # 4. Benefits
        if not context.analysis_results or not context.analysis_results.benefits:
            errors.append("Benefits extraction failed or empty")
            context.log_decision(
                "ValidationAgent", "FAIL: Benefits extraction returned empty list"
            )
            needs_retry = True

        # 5. FAQ Count
        faq_count = (
            len(context.generated_questions) if context.generated_questions else 0
        )
        if faq_count < self.MIN_FAQ_QUESTIONS:
            errors.append(
                f"Insufficient FAQ questions: {faq_count} < {self.MIN_FAQ_QUESTIONS}"
            )
            context.log_decision(
                "ValidationAgent",
                f"FAIL: FAQ count check failed ({faq_count}/{self.MIN_FAQ_QUESTIONS}). Requesting RETRY.",
            )
            needs_retry = True
        else:
            context.log_decision(
                "ValidationAgent", f"PASS: FAQ count OK ({faq_count} questions)"
            )

        # 6. Comparison Data (optional but logged)
        if not context.comparison_data:
            context.log_decision(
                "ValidationAgent",
                "INFO: No comparison data - comparison page will be skipped",
            )

        context.validation_errors = errors
        context.is_valid = len(errors) == 0

        if context.is_valid:
            context.log_decision(
                "ValidationAgent", "PASS: All validation checks passed"
            )
            return self.create_result(
                AgentStatus.CONTINUE, context, "Validation passed"
            )
        elif needs_retry:
            return self.create_result(
                AgentStatus.RETRY, context, f"Retry needed: {', '.join(errors)}"
            )
        else:
            return self.create_result(
                AgentStatus.VALIDATION_FAILED,
                context,
                f"Validation failed: {', '.join(errors)}",
            )


class GenerationAgent(BaseAgent):
    """
    Responsible for rendering templates and saving files.
    Goal: "Complete Content Generation" - autonomously decides what to generate.
    """

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not context.is_valid:
            return self.create_result(
                AgentStatus.ERROR, context, "Cannot generate: Context is invalid"
            )

        logger.info("GenerationAgent: Determining what to generate...")

        try:
            import json
            from datetime import datetime
            from pathlib import Path

            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            product = context.product_data.model_dump()
            analysis = context.analysis_results.model_dump()

            # --- AUTONOMOUS DECISION: What outputs are needed? ---
            outputs_generated = []

            # 1. FAQ Page (if we have questions)
            if context.generated_questions:
                context.log_decision(
                    "GenerationAgent", "Generating FAQ page (questions available)"
                )
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

            # 2. Product Page (always generate if product data exists)
            if product:
                context.log_decision("GenerationAgent", "Generating Product page")
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
                    "side_effects": product.get("side_effects", "None reported"),
                }
                product_template = ProductPageTemplate()
                prod_output = product_template.render(product_page_data)
                with open(output_dir / "product_page.json", "w", encoding="utf-8") as f:
                    json.dump(prod_output, f, indent=2, ensure_ascii=False)
                outputs_generated.append("product_page.json")

            # 3. Comparison Page (if comparison data exists)
            if context.comparison_data and analysis.get("comparison"):
                context.log_decision(
                    "GenerationAgent",
                    "Generating Comparison page (comparison data available)",
                )
                comp = analysis["comparison"]
                product_b = context.comparison_data.model_dump()

                differences = [
                    {
                        "aspect": "Ingredients",
                        "details": (
                            f"Common: {', '.join(comp['ingredients']['common_ingredients'])}. "
                            f"{product['name']} unique: {', '.join(comp['ingredients']['unique_to_a'])}. "
                            f"{product_b['name']} unique: {', '.join(comp['ingredients']['unique_to_b'])}."
                        ),
                    },
                    {
                        "aspect": "Price",
                        "details": (
                            f"₹{comp['price']['difference']} difference "
                            f"({comp['price']['percentage_difference']}%). "
                            f"{comp['price']['cheaper_product']} is more affordable."
                        ),
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

            return self.create_result(
                AgentStatus.COMPLETE,
                context,
                f"Generated: {', '.join(outputs_generated)}",
            )

        except Exception as e:
            logger.exception("Generation failed")
            return self.create_result(AgentStatus.ERROR, context, str(e))
