"""
Verifier Agent: Independent auditor for post-generation verification.
Distinct from ValidationWorker - this agent critically evaluates final outputs.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from skincare_agent_system.actors.agents import BaseAgent
from skincare_agent_system.core.context_analyzer import get_context_analyzer
from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
)
from skincare_agent_system.core.proposals import AgentProposal
from skincare_agent_system.security.guardrails import Guardrails

logger = logging.getLogger("Verifier")


class VerifierAgent(BaseAgent):
    """
    Independent Verifier Agent.
    Performs post-generation verification to ensure outputs meet quality and
    safety standards.
    Proposes action when generation is complete but not verified.
    """

    MIN_CONTENT_LENGTH: int = 50
    MAX_CONTENT_LENGTH: int = 100000

    HARMFUL_PATTERNS: List[re.Pattern] = [
        re.compile(
            r"\b(kill|harm|damage|destroy)\s+(skin|yourself|user)", re.IGNORECASE
        ),
        re.compile(r"\b(never|don\'t)\s+use\s+sunscreen", re.IGNORECASE),
        re.compile(r"\b(ingest|drink|eat)\s+(serum|cream|lotion)", re.IGNORECASE),
    ]

    def __init__(self, name: str = "VerifierAgent"):
        super().__init__(
            name,
            role="Independent Auditor",
            backstory=(
                "Critical evaluator who independently verifies outputs. "
                "Never trusts, always verifies."
            ),
        )
        self._verified = False

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if generation complete but not verified."""
        output_dir = Path("output")
        outputs_exist = (output_dir / "faq.json").exists() and (
            output_dir / "product_page.json"
        ).exists()
        return context.is_valid and outputs_exist and not self._verified

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to verify if outputs exist - DYNAMIC scoring."""
        analyzer = get_context_analyzer()

        if not context.is_valid:
            return AgentProposal(
                agent_name=self.name,
                action="verify",
                confidence=0.0,
                reason="Need validated context first",
                preconditions_met=False,
            )

        output_dir = Path("output")
        outputs_exist = (output_dir / "faq.json").exists() and (
            output_dir / "product_page.json"
        ).exists()

        if not outputs_exist:
            return AgentProposal(
                agent_name=self.name,
                action="verify",
                confidence=0.0,
                reason="Need generated outputs first",
                preconditions_met=False,
            )

        if self._verified:
            return AgentProposal(
                agent_name=self.name,
                action="verify",
                confidence=0.0,
                reason="Already verified",
                preconditions_met=False,
            )

        # Calculate dynamic confidence and priority
        base_confidence = 0.90  # High base for ready outputs
        bonus = analyzer.get_context_bonus(self.name, context)
        confidence = min(1.0, max(0.0, base_confidence + bonus))
        priority = analyzer.get_base_priority(self.name, context)

        return AgentProposal(
            agent_name=self.name,
            action="verify_outputs",
            confidence=confidence,
            reason=(
                "Outputs generated - I can perform independent verification "
                f"(conf: {confidence:.2f})"
            ),
            preconditions_met=True,
            priority=priority,
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """
        Perform post-generation verification.

        Checks:
        1. Content accuracy (basic structure validation)
        2. Safety checks (no PII, no harmful content)
        3. Schema compliance
        """
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Starting independent verification...")

        # Use SelfReflector for standardized critique
        from skincare_agent_system.cognition.reflection import SelfReflector

        reflector = SelfReflector()
        verification_issues: List[str] = []

        # 1. Reflect on Data
        data_reflection = reflector.reflect_on_output("DataAgent", None, context)
        for issue in data_reflection.issues:
            verification_issues.append(f"{issue.severity.upper()}: {issue.description}")

        # 2. Reflect on Analysis
        analysis_reflection = reflector.reflect_on_output(
            "AnalysisAgent", None, context
        )
        for issue in analysis_reflection.issues:
            verification_issues.append(f"{issue.severity.upper()}: {issue.description}")

        # 3. Reflect on Generation (Files)
        gen_reflection = reflector.reflect_on_output("GenerationAgent", None, context)
        for issue in gen_reflection.issues:
            verification_issues.append(f"{issue.severity.upper()}: {issue.description}")

        # 4. Custom Safety Checks (keep local strict logic)
        safety_issues = self._verify_safety(context)
        verification_issues.extend(safety_issues)

        # 5. Local Question Verification (augmentation)
        if context.generated_questions:
            q_issues = self._verify_questions(context.generated_questions)
            verification_issues.extend(q_issues)

        # Log all issues
        for issue in verification_issues:
            context.log_decision(self.name, f"VERIFICATION: {issue}")

        # Determine result
        critical_issues = [i for i in verification_issues if i.startswith("CRITICAL")]

        if critical_issues:
            logger.error(f"Verification FAILED: {len(critical_issues)} critical issues")
            return self.create_result(
                AgentStatus.ERROR,
                context,
                f"Verification failed: {len(critical_issues)} critical issues",
            )

        if verification_issues:
            logger.warning(
                f"Verification passed with {len(verification_issues)} warnings"
            )
            context.log_decision(
                self.name, f"PASS (with {len(verification_issues)} warnings)"
            )
        else:
            logger.info("Verification passed with no issues")
            context.log_decision(self.name, "PASS: All verification checks complete")

        self._verified = True
        return self.create_result(
            AgentStatus.COMPLETE, context, "Verification complete"
        )

    def _verify_product_data(self, product: Dict[str, Any]) -> List[str]:
        """Verify product data structure and content."""
        issues = []

        # Required fields
        required_fields = ["name", "brand", "key_ingredients"]
        for field in required_fields:
            if not product.get(field):
                issues.append(f"CRITICAL: Product missing required field '{field}'")

        # Name length check
        if product.get("name") and len(product["name"]) < 3:
            issues.append("WARNING: Product name suspiciously short")

        # Price sanity check
        price = product.get("price", 0)
        if price and (price < 0 or price > 1000000):
            issues.append(f"WARNING: Product price seems unrealistic: {price}")

        return issues

    def _verify_analysis_results(self, analysis: Dict[str, Any]) -> List[str]:
        """Verify analysis results."""
        issues = []

        # Benefits should not be empty
        benefits = analysis.get("benefits", [])
        if not benefits:
            issues.append("CRITICAL: No benefits extracted")
        elif len(benefits) < 2:
            issues.append("WARNING: Very few benefits extracted")

        # Usage should exist
        usage = analysis.get("usage", "")
        if not usage:
            issues.append("WARNING: No usage instructions extracted")

        return issues

    def _verify_questions(self, questions: List[Any]) -> List[str]:
        """Verify generated questions."""
        issues = []

        if len(questions) < 10:
            issues.append(
                f"WARNING: Only {len(questions)} questions generated (expected 15+)"
            )

        # Check for duplicate questions
        question_texts = [
            q[0] if isinstance(q, (list, tuple)) else str(q) for q in questions
        ]
        unique_questions = set(question_texts)
        if len(unique_questions) < len(question_texts):
            duplicate_count = len(question_texts) - len(unique_questions)
            issues.append(f"WARNING: {duplicate_count} duplicate questions detected")

        # Check question quality (basic)
        for i, q in enumerate(questions):
            q_text = q[0] if isinstance(q, (list, tuple)) else str(q)
            if len(q_text) < 10:
                issues.append(f"WARNING: Question {i+1} is too short: '{q_text}'")
            if "?" not in q_text:
                issues.append(
                    f"WARNING: Question {i+1} doesn't end with '?': '{q_text[:50]}'"
                )

        return issues

    def _verify_safety(self, context: AgentContext) -> List[str]:
        """Perform safety verification on all content."""
        issues = []

        # Collect all text content
        all_text = []

        if context.product_data:
            all_text.append(context.product_data.name or "")
            all_text.append(context.product_data.side_effects or "")
            all_text.append(context.product_data.usage_instructions or "")

        if context.analysis_results:
            all_text.extend(context.analysis_results.benefits or [])
            all_text.append(context.analysis_results.usage or "")

        if context.generated_questions:
            for q in context.generated_questions:
                if isinstance(q, (list, tuple)) and len(q) >= 2:
                    all_text.append(str(q[0]))  # Question
                    all_text.append(str(q[1]))  # Answer

        combined_text = " ".join(all_text)

        # Check for harmful patterns
        for pattern in self.HARMFUL_PATTERNS:
            match = pattern.search(combined_text)
            if match:
                issues.append(f"CRITICAL: Harmful content detected: '{match.group()}'")

        # Check for PII using Guardrails
        is_safe, error = Guardrails.check_output_safety(combined_text)
        if not is_safe:
            issues.append(f"CRITICAL: {error}")

        return issues
