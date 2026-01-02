"""
Delegator Agent: Manages distribution of tasks to workers.
Now with LLM-powered task reasoning and delegation.
"""

import logging
import os
from typing import Optional

from skincare_agent_system.actors.agents import BaseAgent
from skincare_agent_system.actors.workers import (
    BenefitsWorker,
    ComparisonWorker,
    QuestionsWorker,
    UsageWorker,
    ValidationWorker,
)
from skincare_agent_system.core.context_analyzer import get_context_analyzer
from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
)
from skincare_agent_system.core.proposals import AgentProposal

logger = logging.getLogger("Delegator")

# Check if LLM is available


class DelegatorAgent(BaseAgent):
    """
    Manages the 'Analysis' phase by delegating to specialized workers.
    Uses LLM for task reasoning when API key is available.
    Falls back to heuristic logic otherwise.
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
        self._llm = None

        # Check availability at runtime, not import time
        self._llm_enabled = os.getenv("MISTRAL_API_KEY") is not None

        # PHASE 4: Track if data events have triggered readiness
        self._data_ready = False
        self._synthetic_ready = False

    def get_event_subscriptions(self):
        """
        PHASE 4: DelegatorAgent subscribes to data-related events.
        When data is loaded, it can begin analysis coordination.
        """
        from skincare_agent_system.core.proposals import EventType

        return [
            EventType.DATA_LOADED,
            EventType.SYNTHETIC_DATA_GENERATED,
        ]

    def on_data_loaded(self, event):
        """FIX: Handle DATA_LOADED event - mark ready and trigger reactivation."""
        self._data_ready = True
        logger.info(f"{self.name} received DATA_LOADED - ready for analysis")
        return True  # Triggers reactivation

    def on_synthetic_data_generated(self, event):
        """FIX: Handle SYNTHETIC_DATA_GENERATED event - trigger reactivation."""
        self._synthetic_ready = True
        logger.info(f"{self.name} received SYNTHETIC_DATA_GENERATED - comparison ready")
        return True  # Triggers reactivation

    def _get_llm(self):
        """Lazy load LLM client."""
        # Re-check env in case it loaded late
        if not self._llm_enabled:
            self._llm_enabled = os.getenv("MISTRAL_API_KEY") is not None

        if self._llm is None and self._llm_enabled:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                self._llm = LLMClient()
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}")
        return self._llm

    def can_handle(self, context: AgentContext) -> bool:
        """Can handle if data exists but analysis not complete."""
        return (
            context.product_data is not None
            and context.comparison_data is not None
            and not context.is_valid
            and not self._completed
        )

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """Propose to run analysis delegation using LLM reasoning if available."""
        # Basic precondition checks
        if context.product_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Need product data first",
                preconditions_met=False,
            )

        if context.comparison_data is None:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Need comparison data first",
                preconditions_met=False,
            )

        if context.is_valid or self._completed:
            return AgentProposal(
                agent_name=self.name,
                action="delegate",
                confidence=0.0,
                reason="Already completed",
                preconditions_met=False,
            )

        # Use LLM for reasoning if available
        llm = self._get_llm()
        if llm:
            return self._propose_with_llm(context, llm)
        else:
            return self._propose_heuristic(context)

    def _propose_with_llm(self, context: AgentContext, llm) -> AgentProposal:
        """Use LLM to reason about delegation."""
        prompt = f"""You are a Project Manager agent deciding whether to delegate analysis tasks.

Current Context:
- Product: {context.product_data.name if context.product_data else 'None'}
- Comparison Product: {context.comparison_data.name if context.comparison_data else 'None'}
- Analysis Done: {'Yes' if context.analysis_results else 'No'}
- Validated: {'Yes' if context.is_valid else 'No'}

Available Workers:
1. BenefitsWorker - Extracts product benefits
2. UsageWorker - Formats usage instructions
3. QuestionsWorker - Generates FAQ questions
4. ComparisonWorker - Creates product comparison
5. ValidationWorker - Validates results

Should I delegate tasks to workers now?

Respond with JSON:
{{
    "should_delegate": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Your reasoning here",
    "tasks_to_run": ["benefits", "usage", "questions", "comparison", "validation"]
}}"""

        try:
            response = llm.generate_json(prompt, agent_identity=f"agent_{self.name}")
            logger.info(f"LLM reasoning: {response.get('reasoning', 'N/A')}")

            confidence = response.get("confidence", 0.87)
            reason = response.get("reasoning", "LLM determined delegation needed")

            context.log_decision(self.name, f"[LLM] {reason}")

            return AgentProposal(
                agent_name=self.name,
                action="delegate_analysis",
                confidence=confidence,
                reason=reason,
                preconditions_met=response.get("should_delegate", True),
                priority=8,
            )
        except Exception as e:
            logger.warning(f"LLM proposal failed, falling back to heuristic: {e}")
            return self._propose_heuristic(context)

    def _propose_heuristic(self, context: AgentContext) -> AgentProposal:
        """Fallback heuristic proposal - DYNAMIC scoring."""
        analyzer = get_context_analyzer()

        # Calculate dynamic confidence and priority
        base_confidence = analyzer.assess_analysis_readiness(context)
        bonus = analyzer.get_context_bonus(self.name, context)
        confidence = min(1.0, max(0.0, base_confidence + bonus))
        priority = analyzer.get_base_priority(self.name, context)

        return AgentProposal(
            agent_name=self.name,
            action="delegate_analysis",
            confidence=confidence,
            reason=f"Data ready - I can coordinate workers for analysis and validation (conf: {confidence:.2f})",
            preconditions_met=True,
            priority=priority,
        )

    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """
        Default execution now uses PARALLEL worker execution.
        Uses asyncio.run() to execute the async version.
        """
        import asyncio

        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # Already in async context, run sync fallback
            return self.run_sync(context, directive)
        except RuntimeError:
            # No event loop, safe to use asyncio.run()
            return asyncio.run(self.run_async(context, directive))

    def run_sync(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """
        PHASE 6: Sync execution now uses PROPOSAL-BASED worker selection.
        Workers compete for tasks via proposals instead of hardcoded order.
        """
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(
            f"{self.name} ({self.role}): Starting PROPOSAL-BASED delegation cycle..."
        )
        context.log_decision(self.name, "Starting proposal-based analysis delegation")

        # Use LLM to plan if available
        llm = self._get_llm()
        if llm:
            plan = self._plan_with_llm(context, llm)
            context.log_decision(self.name, f"[LLM PLAN] {plan}")

        sub_directive = TaskDirective(
            description="Execute domain specific analysis", priority=TaskPriority.SYSTEM
        )

        # Define required task types (order doesn't matter - proposals decide!)
        required_tasks = [
            "extract_benefits",
            "format_usage",
            "generate_faqs",
            "compare_products",
        ]

        for attempt in range(self.max_retries):
            # PHASE 6: Collect proposals from workers for each task
            for task_type in required_tasks:
                best_worker = self._select_worker_by_proposal(task_type, context)
                if best_worker:
                    context.log_decision(
                        self.name,
                        f"Task '{task_type}' assigned to {best_worker} via proposal",
                    )
                    self._run_worker(best_worker, context, sub_directive)
                else:
                    # Fallback to task-name mapping if no proposals
                    fallback_worker = self._get_fallback_worker(task_type)
                    if fallback_worker:
                        context.log_decision(
                            self.name,
                            f"Task '{task_type}' assigned to {fallback_worker} (fallback)",
                        )
                        self._run_worker(fallback_worker, context, sub_directive)

            # Validation always runs at the end
            self._run_worker("validation", context, sub_directive)

            if context.is_valid:
                context.log_decision(
                    self.name, f"Cycle {attempt+1}: Validation passed (proposal-based)."
                )
                self._completed = True
                return self.create_result(
                    AgentStatus.COMPLETE,
                    context,
                    "Proposal-based delegation cycle complete and validated",
                )

            # Use LLM to reflect on failure if available
            if llm:
                reflection = self._reflect_with_llm(context, attempt, llm)
                context.log_decision(self.name, f"[LLM REFLECTION] {reflection}")

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

    async def run_async(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """Async version with parallel worker execution via WORKER PROPOSALS."""
        if not self.validate_instruction(directive):
            return self.create_result(
                AgentStatus.ERROR, context, "Instruction validation failed."
            )

        logger.info(
            f"{self.name} ({self.role}): Starting PARALLEL delegation with worker proposals..."
        )
        context.log_decision(
            self.name, "Starting parallel analysis delegation with worker autonomy"
        )

        # Use LLM to plan if available
        llm = self._get_llm()
        if llm:
            plan = self._plan_with_llm(context, llm)
            context.log_decision(self.name, f"[LLM PLAN] {plan}")

        sub_directive = TaskDirective(
            description="Execute domain specific analysis", priority=TaskPriority.SYSTEM
        )

        # Define available tasks
        available_tasks = [
            "extract_benefits",
            "format_usage",
            "generate_faqs",
            "compare_products",
        ]

        for attempt in range(self.max_retries):
            # PHASE 1: Collect worker proposals for each task
            worker_assignments = []
            for task_type in available_tasks:
                best_worker = None
                best_confidence = 0.0

                for worker_key, worker in self.workers.items():
                    if worker_key == "validation":
                        continue  # Validation runs after parallel tasks
                    proposal = worker.propose_for_task(task_type, context)
                    if (
                        proposal
                        and proposal.preconditions_met
                        and proposal.confidence > best_confidence
                    ):
                        best_worker = worker_key
                        best_confidence = proposal.confidence

                if best_worker:
                    worker_assignments.append((best_worker, task_type, best_confidence))
                    logger.info(
                        f"Task '{task_type}' assigned to {best_worker} (conf: {best_confidence:.2f})"
                    )

            # PHASE 2: Run assigned workers in PARALLEL
            import asyncio

            tasks = [
                self._run_worker_async(worker_key, context, sub_directive)
                for worker_key, task_type, conf in worker_assignments
            ]

            # Execute concurrently
            logger.info(
                f"Executing {len(tasks)} workers in parallel (proposal-based)..."
            )
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Worker {i} failed: {result}")

            # Validate
            await self._run_worker_async("validation", context, sub_directive)

            if context.is_valid:
                context.log_decision(
                    self.name,
                    f"Cycle {attempt+1}: Validation passed (parallel execution).",
                )
                self._completed = True
                return self.create_result(
                    AgentStatus.COMPLETE,
                    context,
                    "Parallel delegation cycle complete and validated",
                )

            # Use LLM to reflect on failure if available
            if llm:
                reflection = self._reflect_with_llm(context, attempt, llm)
                context.log_decision(self.name, f"[LLM REFLECTION] {reflection}")

            logger.warning(
                f"Validation failed attempt {attempt+1}: {context.validation_errors}"
            )
            context.log_decision(
                self.name, f"Cycle {attempt+1}: Validation failed. Retrying..."
            )

        self._completed = True
        return self.create_result(
            AgentStatus.VALIDATION_FAILED, context, "Max retries reached"
        )

    def _plan_with_llm(self, context: AgentContext, llm) -> str:
        """Use LLM to create execution plan."""
        prompt = f"""You are a Project Manager planning task delegation.

Product: {context.product_data.name}
Comparison: {context.comparison_data.name}

Create a brief execution plan (2-3 sentences) for:
1. Extracting benefits
2. Formatting usage
3. Generating 15+ FAQ questions
4. Creating comparison
5. Validating results

Be concise."""

        try:
            return llm.generate(prompt, temperature=0.5)[:200]
        except Exception as e:
            return f"Using default plan (LLM error: {e})"

    def _reflect_with_llm(self, context: AgentContext, attempt: int, llm) -> str:
        """Use LLM to reflect on validation failure."""
        prompt = f"""Validation failed on attempt {attempt + 1}.
Errors: {context.validation_errors}

Why might this have failed? What should be adjusted? (1-2 sentences)"""

        try:
            return llm.generate(prompt, temperature=0.3)[:150]
        except Exception:
            return "Retrying with same strategy"

    def _run_worker(
        self, worker_key: str, context: AgentContext, directive: TaskDirective
    ) -> AgentResult:
        worker = self.workers[worker_key]
        return worker.run(context, directive)

    async def _run_worker_async(
        self, worker_key: str, context: AgentContext, directive: TaskDirective
    ) -> AgentResult:
        """Run worker asynchronously."""
        import asyncio

        worker = self.workers[worker_key]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, worker.run, context, directive)

    def _select_worker_by_proposal(
        self, task_type: str, context: AgentContext
    ) -> Optional[str]:
        """
        PHASE 6: Select best worker for a task via proposals.
        Workers bid for tasks based on their specializations.
        """
        best_worker = None
        best_confidence = 0.0

        for worker_key, worker in self.workers.items():
            if worker_key == "validation":
                continue  # Validation runs separately

            # Ask worker to propose for this task
            proposal = worker.propose_for_task(task_type, context)
            if (
                proposal
                and proposal.preconditions_met
                and proposal.confidence > best_confidence
            ):
                best_worker = worker_key
                best_confidence = proposal.confidence
                logger.debug(
                    f"Worker {worker_key} bid {proposal.confidence:.2f} for {task_type}"
                )

        if best_worker:
            logger.info(
                f"Selected {best_worker} for '{task_type}' (confidence: {best_confidence:.2f})"
            )
        return best_worker

    def _get_fallback_worker(self, task_type: str) -> Optional[str]:
        """
        PHASE 6: Fallback mapping from task type to worker.
        Used when no proposals are available.
        """
        fallback_map = {
            "extract_benefits": "benefits",
            "analyze_ingredients": "benefits",
            "format_usage": "usage",
            "extract_usage": "usage",
            "generate_faqs": "questions",
            "create_questions": "questions",
            "compare_products": "comparison",
            "product_comparison": "comparison",
        }
        return fallback_map.get(task_type)
