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
from ..core.proposals import AgentProposal

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
    """Extract and analyze product benefits with explicit goals"""
    
    SPECIALIZATIONS = ["extract_benefits", "analyze_ingredients", "benefits"]
    
    def __init__(self, name: str = "BenefitsWorker"):
        super().__init__(name=name, role="Benefits Analyst")
        self._init_goals()
    
    def _init_goals(self):
        """Initialize goals for benefits extraction"""
        self.goals = [
            {
                "description": "Extract at least 3 key benefits from product data",
                "check": lambda ctx: (
                    ctx.analysis_results is not None
                    and len(ctx.analysis_results.benefits) >= 3
                ),
                "priority": 8
            },
            {
                "description": "Ensure benefits are substantiated by ingredients",
                "check": lambda ctx: self._benefits_match_ingredients(ctx),
                "priority": 6
            },
            {
                "description": "Format benefits for consumer clarity",
                "check": lambda ctx: (
                    ctx.analysis_results is not None
                    and all(len(b) > 10 for b in ctx.analysis_results.benefits)
                ),
                "priority": 4
            }
        ]
    
    def _benefits_match_ingredients(self, context: AgentContext) -> bool:
        """Check if extracted benefits align with ingredients"""
        if context.analysis_results is None:
            return False
        benefits = context.analysis_results.benefits or []
        ingredients = context.product_data.key_ingredients if context.product_data else []
        
        # Simple check: at least one benefit mentions an ingredient
        return any(
            any(ing.lower() in benefit.lower() for ing in ingredients)
            for benefit in benefits
        )
    
    def assess_context(self, context: AgentContext) -> Dict[str, Any]:
        """Assess context for benefits extraction"""
        has_data = context.product_data is not None
        already_done = (
            context.analysis_results is not None 
            and len(context.analysis_results.benefits) > 0
        )
        
        if not has_data:
            return {
                "should_act": False,
                "confidence": 0.0,
                "reasoning": "No product data available - cannot extract benefits"
            }
        
        if already_done:
            return {
                "should_act": False,
                "confidence": 0.0,
                "reasoning": "Benefits already extracted"
            }
        
        # Calculate confidence based on data quality
        benefits_list = context.product_data.benefits or []
        total_len = sum(len(str(b)) for b in benefits_list)
        complexity = "high" if total_len > 200 else "medium" if total_len > 50 else "low"
        confidence_map = {"low": 0.95, "medium": 0.85, "high": 0.75}
        
        return {
            "should_act": True,
            "confidence": confidence_map[complexity],
            "reasoning": f"Product data available. Complexity: {complexity}. Ready to extract benefits."
        }
    
    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """Execute benefits extraction with goal-driven approach"""
        logger.info(f"{self.name}: Extracting benefits...")
        
        assessment = self.assess_context(context)
        if not assessment['should_act']:
            return self.create_result(
                AgentStatus.COMPLETE, context, assessment['reasoning']
            )
        
        try:
            product_dict = context.product_data.model_dump()
            benefits = extract_benefits(product_dict)

            if not context.analysis_results:
                context.analysis_results = AnalysisResults(
                    benefits=[], usage="", comparison={}
                )

            context.analysis_results.benefits = benefits
            
            # Check goals after execution
            goals_met = sum(1 for g in self.goals if g['check'](context))
            logger.info(f"{self.name}: {goals_met}/{len(self.goals)} goals met")
            
            return self.create_result(
                AgentStatus.COMPLETE, context, 
                f"Extracted {len(benefits)} benefits ({goals_met}/{len(self.goals)} goals met)"
            )
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return self.create_result(AgentStatus.ERROR, context, str(e))
    
    def propose_for_task(self, task_type: str, context: AgentContext):
        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Benefits specialist",
                preconditions_met=True,
            )
        return None

    def propose(self, context: AgentContext) -> AgentProposal:
        """Propose benefits extraction using goal-driven assessment"""
        assessment = self.assess_context(context)
        
        if not assessment['should_act']:
            return AgentProposal(
                agent_name=self.name,
                action="extract_benefits",
                confidence=0.0,
                reason=assessment['reasoning'],
                preconditions_met=False,
                priority=0
            )
        
        return AgentProposal(
            agent_name=self.name,
            action="extract_benefits",
            confidence=assessment['confidence'],
            reason=assessment['reasoning'],
            preconditions_met=True,
            priority=7
        )



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
        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None

    def propose(self, context: AgentContext) -> AgentProposal:
        """Propose usage extraction"""
        has_data = context.product_data is not None
        already_done = (
            context.analysis_results is not None 
            and context.analysis_results.usage
        )
        
        if not has_data:
            return AgentProposal(
                agent_name=self.name,
                action="extract_usage",
                confidence=0.0,
                reason="No product data",
                preconditions_met=False,
                priority=0
            )
        
        if already_done:
            return AgentProposal(
                agent_name=self.name,
                action="extract_usage",
                confidence=0.0,
                reason="Usage already extracted",
                preconditions_met=True,
                priority=0
            )
        
        return AgentProposal(
            agent_name=self.name,
            action="extract_usage",
            confidence=0.85,
            reason="Product data available, ready to extract usage",
            preconditions_met=True,
            priority=5
        )


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
        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None

    def propose(self, context: AgentContext) -> AgentProposal:
        """Propose question generation"""
        has_data = context.product_data is not None
        already_done = len(context.generated_questions) >= self.MIN_QUESTIONS
        
        if not has_data:
            return AgentProposal(
                agent_name=self.name,
                action="generate_faqs",
                confidence=0.0,
                reason="No product data",
                preconditions_met=False,
                priority=0
            )
        
        if already_done:
            return AgentProposal(
                agent_name=self.name,
                action="generate_faqs",
                confidence=0.0,
                reason=f"Already have {len(context.generated_questions)} questions",
                preconditions_met=True,
                priority=0
            )
        
        return AgentProposal(
            agent_name=self.name,
            action="generate_faqs",
            confidence=0.80,
            reason="Ready to generate FAQ questions",
            preconditions_met=True,
            priority=6
        )


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
        if task_type in self.SPECIALIZATIONS:
            return AgentProposal(
                agent_name=self.name,
                action=task_type,
                confidence=0.9,
                reason="Specialist",
                preconditions_met=True,
            )
        return None

    def propose(self, context: AgentContext) -> AgentProposal:
        """Propose product comparison"""
        has_both = (
            context.product_data is not None 
            and context.comparison_data is not None
        )
        already_done = (
            context.analysis_results is not None 
            and context.analysis_results.comparison
        )
        
        if not has_both:
            return AgentProposal(
                agent_name=self.name,
                action="compare_products",
                confidence=0.0,
                reason="Need both products for comparison",
                preconditions_met=False,
                priority=0
            )
        
        if already_done:
            return AgentProposal(
                agent_name=self.name,
                action="compare_products",
                confidence=0.0,
                reason="Comparison already complete",
                preconditions_met=True,
                priority=0
            )
        
        return AgentProposal(
            agent_name=self.name,
            action="compare_products",
            confidence=0.82,
            reason="Both products available, ready to compare",
            preconditions_met=True,
            priority=5
        )


class ValidationWorker(BaseAgent):
    """Reactive validation worker with event subscriptions"""

    MIN_FAQ_QUESTIONS = 15  # ✅ FIX: Was 10, now 15
    SPECIALIZATIONS = ["validate_results", "quality_check", "validation"]

    def __init__(self, name: str = "ValidationWorker"):
        super().__init__(name=name, role="Quality Validator")
        self._should_repropose = False
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        """Subscribe to relevant events for reactive behavior"""
        try:
            from ..core.event_system import get_event_bus, EventType

            bus = get_event_bus()

            # React when generation completes
            bus.subscribe(
                EventType.GENERATION_COMPLETE,
                self._on_generation_complete,
                self.name,
                priority=10  # High priority - validation is critical
            )

            # React when analysis completes
            bus.subscribe(
                EventType.ANALYSIS_COMPLETE,
                self._on_analysis_complete,
                self.name,
                priority=5
            )

            logger.info(f"{self.name}: Event subscriptions registered")
        except Exception as e:
            logger.warning(f"{self.name}: Could not setup subscriptions: {e}")

    def _on_generation_complete(self, event) -> bool:
        """
        React to generation completion.
        Returns True if this agent wants to propose action (validate).
        """
        logger.info(f"{self.name} reacting to {event.type.value}")

        # Check if validation is needed
        if not event.data.get('already_validated'):
            logger.info(f"{self.name} requests re-proposal for validation")
            self._should_repropose = True
            return True  # Request re-proposal

        return False

    def _on_analysis_complete(self, event) -> bool:
        """React to analysis completion - prepare for validation"""
        logger.info(f"{self.name} reacting to {event.type.value}")
        # Mark that we're ready to validate
        self._should_repropose = True
        return True

    def _on_validation_failed(self, event) -> bool:
        """React to validation failure - trigger retry logic"""
        error_type = event.data.get('error_type')

        if error_type == 'insufficient_questions':
            logger.info(f"{self.name}: Detected insufficient questions, requesting regeneration")
            # Publish event to trigger regeneration
            from ..core.event_system import publish_event, EventType
            publish_event(
                EventType.RETRY_REQUESTED,
                self.name,
                {
                    'error': 'insufficient_questions',
                    'required_action': 'regenerate_questions',
                    'min_required': self.MIN_FAQ_QUESTIONS
                }
            )
            return True

        return False

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

        # Publish validation result event
        try:
            from ..core.event_system import publish_event, EventType
            if context.is_valid:
                publish_event(EventType.VALIDATION_PASSED, self.name, {"errors": []})
            else:
                publish_event(
                    EventType.VALIDATION_FAILED,
                    self.name,
                    {"errors": errors, "error_type": self._classify_error(errors)}
                )
        except Exception as e:
            logger.warning(f"Could not publish validation event: {e}")

        if context.is_valid:
            return self.create_result(
                AgentStatus.COMPLETE, context, "Validation passed"
            )
        else:
            return self.create_result(
                AgentStatus.VALIDATION_FAILED, context, f"Validation failed: {errors}"
            )

    def _classify_error(self, errors: List[str]) -> str:
        """Classify error type for reactive handling"""
        for error in errors:
            if "questions" in error.lower():
                return "insufficient_questions"
            if "benefits" in error.lower():
                return "missing_benefits"
            if "product" in error.lower():
                return "missing_product"
        return "unknown"

    def propose(self, context: AgentContext) -> AgentProposal:
        """Generate proposal with reactive awareness"""
        # Check if we were triggered by an event
        if self._should_repropose:
            self._should_repropose = False
            return AgentProposal(
                agent_name=self.name,
                action="validate_results",
                confidence=0.95,  # High confidence - validation is critical
                reason="Reactive: Triggered by analysis/generation completion event",
                preconditions_met=True,
                priority=8
            )

        # Normal proposal logic
        has_data = context.analysis_results is not None
        already_valid = context.is_valid

        if not has_data:
            return AgentProposal(
                agent_name=self.name,
                action="validate_results",
                confidence=0.0,
                reason="No analysis results to validate",
                preconditions_met=False,
                priority=0
            )

        if already_valid:
            return AgentProposal(
                agent_name=self.name,
                action="validate_results",
                confidence=0.0,
                reason="Already validated successfully",
                preconditions_met=True,
                priority=0
            )

        return AgentProposal(
            agent_name=self.name,
            action="validate_results",
            confidence=0.85,
            reason="Analysis results available, validation needed",
            preconditions_met=True,
            priority=7
        )

