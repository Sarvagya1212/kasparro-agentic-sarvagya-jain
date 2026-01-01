"""
Verifier Agent: Independent auditor for post-generation verification.
Distinct from ValidationWorker - this agent critically evaluates final outputs.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .agents import BaseAgent
from .guardrails import Guardrails
from .models import AgentContext, AgentResult, AgentStatus, TaskDirective

logger = logging.getLogger("Verifier")


class VerifierAgent(BaseAgent):
    """
    Independent Verifier Agent.
    Performs post-generation verification to ensure outputs meet quality and safety standards.
    This is separate from ValidationWorker to follow the principle:
    "Do not rely on the generating agent to check its own work."
    """

    # Quality thresholds
    MIN_CONTENT_LENGTH: int = 50
    MAX_CONTENT_LENGTH: int = 100000

    # Harmful content patterns
    HARMFUL_PATTERNS: List[re.Pattern] = [
        re.compile(
            r"\b(kill|harm|damage|destroy)\s+(skin|yourself|user)", re.IGNORECASE
        ),
        re.compile(r"\b(never|don\'t)\s+use\s+sunscreen", re.IGNORECASE),
        re.compile(r"\b(ingest|drink|eat)\s+(serum|cream|lotion)", re.IGNORECASE),
    ]

    def __init__(self, name: str):
        super().__init__(
            name,
            role="Independent Auditor",
            backstory="Critical evaluator who independently verifies outputs meet quality and safety standards. Never trusts, always verifies.",
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

        verification_issues: List[str] = []

        # 1. Verify product data exists and is complete
        if context.product_data:
            product_issues = self._verify_product_data(
                context.product_data.model_dump()
            )
            verification_issues.extend(product_issues)
        else:
            verification_issues.append("CRITICAL: No product data found in context")

        # 2. Verify analysis results
        if context.analysis_results:
            analysis_issues = self._verify_analysis_results(
                context.analysis_results.model_dump()
            )
            verification_issues.extend(analysis_issues)
        else:
            verification_issues.append("CRITICAL: No analysis results found")

        # 3. Verify generated questions
        if context.generated_questions:
            question_issues = self._verify_questions(context.generated_questions)
            verification_issues.extend(question_issues)
        else:
            verification_issues.append("WARNING: No generated questions found")

        # 4. Safety check on all text content
        safety_issues = self._verify_safety(context)
        verification_issues.extend(safety_issues)

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
