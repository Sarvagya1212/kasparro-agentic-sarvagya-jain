"""
Delegator Agent: Manages the distribution of tasks to workers.
Acts as a middle-manager between the Coordinator (Orchestrator) and Workers.
"""

import logging
from typing import Dict, List, Optional

from .agents import BaseAgent
from .models import AgentContext, AgentResult, AgentStatus, TaskDirective, TaskPriority
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
    """

    def __init__(self, name: str):
        super().__init__(
            name,
            role="Project Manager",
            backstory="Efficient Project Manager who balances speed with quality, coordinating specialized workers to deliver complete analysis.",
        )
        # Initialize workers
        self.workers = {
            "benefits": BenefitsWorker("BenefitsWorker"),
            "usage": UsageWorker("UsageWorker"),
            "questions": QuestionsWorker("QuestionsWorker"),
            "comparison": ComparisonWorker("ComparisonWorker"),
            "validation": ValidationWorker("ValidationWorker"),
        }
        self.max_retries = 3

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        if not self.validate_instruction(directive):
            # If high-priority system directive fails, we might hard stop
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(f"{self.name} ({self.role}): Starting delegation cycle...")
        context.log_decision(self.name, "Starting analysis delegation cycle")

        # Create standard directives for sub-workers (Internal priority)
        sub_directive = TaskDirective(
            description="Execute domain specific analysis", priority=TaskPriority.SYSTEM
        )

        # Retry loop for quality assurance
        for attempt in range(self.max_retries):
            # 1. Run Analysis Workers
            self._run_worker("benefits", context, sub_directive)
            self._run_worker("usage", context, sub_directive)
            self._run_worker("questions", context, sub_directive)
            self._run_worker("comparison", context, sub_directive)

            # 2. Run Validation
            val_result = self._run_worker("validation", context, sub_directive)

            if context.is_valid:
                context.log_decision(
                    self.name, f"Cycle {attempt+1}: Validation passed."
                )
                return self.create_result(
                    AgentStatus.COMPLETE,
                    context,
                    "Delegation cycle complete and validated",
                )

            # If invalid, log and retry
            logger.warning(
                f"Validation failed on attempt {attempt+1}. Errors: {context.validation_errors}"
            )
            context.log_decision(
                self.name, f"Cycle {attempt+1}: Validation failed. Retrying..."
            )

        # If we exit loop, we failed
        return self.create_result(
            AgentStatus.VALIDATION_FAILED, context, "Max retries reached in delegation"
        )

    def _run_worker(
        self, worker_key: str, context: AgentContext, directive: TaskDirective
    ) -> AgentResult:
        worker = self.workers[worker_key]
        return worker.run(context, directive)
