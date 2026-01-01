"""
Delegator Agent: Manages distribution of tasks to workers.
Supports proposal-based coordination.
"""

import logging
from typing import Optional

from .agents import BaseAgent
from .models import AgentContext, AgentResult, AgentStatus, TaskDirective, TaskPriority
from .proposals import AgentProposal
from .workers import (
    BenefitsWorker,
    ComparisonWorker,
    QuestionsWorker,
    UsageWorker,
    ValidationWorker,
)

logger = logging.getLogger("Delegator")


class DelegatorAgent(BaseAgent):
    """
    Manages the 'Analysis' phase by delegating to specialized workers.
    Proposes action when data exists but no analysis done.
    """

    def __init__(self, name: str = "DelegatorAgent"):
        super().__init__(
            name,
            role="Project Manager",
            backstory="Efficient PM who coordinates workers to deliver complete analysis.",
        )
        self.workers = {
            "benefits": BenefitsWorker("BenefitsWorker"),
            "usage": UsageWorker("UsageWorker"),
            "questions": QuestionsWorker("QuestionsWorker"),
            "comparison": ComparisonWorker("ComparisonWorker"),
            "validation": ValidationWorker("ValidationWorker"),
        }
        self.max_retries = 3
        self._completed = False

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if data exists but analysis not complete."""
        return (
            context.product_data is not None and
            context.comparison_data is not None and
            not context.is_valid and
            not self._completed
        )

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to run analysis delegation."""
        if context.product_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Need product data first",
                preconditions_met=False
            )

        if context.comparison_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Need comparison data first",
                preconditions_met=False
            )

        if context.is_valid:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Already validated",
                preconditions_met=False
            )

        if self._completed:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Already completed delegation",
                preconditions_met=False
            )

        return AgentProposal(
            agent_name=self.name,
            action="delegate_analysis",
            confidence=0.87,
            reason="Data ready - I can coordinate workers for analysis and validation",
            preconditions_met=True,
            priority=8
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Starting delegation cycle...")
        context.log_decision(self.name, "Starting analysis delegation cycle")

        sub_directive = TaskDirective(
            description="Execute domain specific analysis", priority=TaskPriority.SYSTEM
        )

        for attempt in range(self.max_retries):
            # Run all workers
            self._run_worker("benefits", context, sub_directive)
            self._run_worker("usage", context, sub_directive)
            self._run_worker("questions", context, sub_directive)
            self._run_worker("comparison", context, sub_directive)

            # Validate
            self._run_worker("validation", context, sub_directive)

            if context.is_valid:
                context.log_decision(
                    self.name, f"Cycle {attempt+1}: Validation passed."
                )
                self._completed = True
                return self.create_result(
                    AgentStatus.COMPLETE,
                    context,
                    "Delegation cycle complete and validated",
                )

            logger.warning(
                f"Validation failed attempt {attempt+1}: {context.validation_errors}"
            )
            context.log_decision(
                self.name, f"Cycle {attempt+1}: Validation failed. Retrying..."
            )

        self._completed = True  # Prevent infinite loops
        return self.create_result(
            AgentStatus.VALIDATION_FAILED, context, "Max retries reached"
        )

    def _run_worker(
        self, worker_key: str, context: AgentContext, directive: TaskDirective
    ) -> AgentResult:
        worker = self.workers[worker_key]
        return worker.run(context, directive)
