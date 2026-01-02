"""
Orchestrator: Stage-based routing with Reflexion self-correction.
Emits events for traceability.
"""

import logging
from typing import Dict, Optional


from skincare_agent_system.core.models import (
    GlobalContext,
    AgentStatus,
    ProcessingStage,
    TaskDirective,
)
from skincare_agent_system.core.proposals import PriorityRouter
from skincare_agent_system.core.event_bus import EventBus, Events

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Orchestrator")


class Orchestrator:
    """
    Stage-based orchestrator with Reflexion self-correction loop.
    """

    MAX_RETRIES = 3

    def __init__(self, max_steps: int = 20):
        self.agents: Dict[str, object] = {}
        self.max_steps = max_steps
        self.router: Optional[PriorityRouter] = None

    def register_agent(self, agent: object):
        """Add agent to pool."""
        self.agents[agent.name] = agent
        logger.info(f"Registered: {agent.name}")

    def run(self, context: GlobalContext) -> GlobalContext:
        """
        Main loop: Check can_handle → Execute → Reflexion on failure.
        """
        logger.info("=== Starting Stage-Based Orchestration ===")
        EventBus.emit(Events.STATE_CHANGE, {"stage": "START"}, context.trace_id)

        if not self.agents:
            raise ValueError("No agents registered")

        self.router = PriorityRouter(list(self.agents.values()))

        step = 0
        while step < self.max_steps:
            step += 1

            # Check if complete
            if context.stage == ProcessingStage.COMPLETE:
                logger.info("Stage=COMPLETE. Done.")
                EventBus.emit(
                    Events.WORKFLOW_COMPLETE, {"steps": step}, context.trace_id
                )
                break

            # Find agent that can_handle current state
            agent = self.router.select_next(context)

            if not agent:
                self._advance_stage_if_stuck(context)
                continue

            # Emit agent start event
            EventBus.emit(
                Events.AGENT_START,
                {
                    "agent": agent.name,
                    "stage": context.stage.value,
                    "retry": context.retry_count,
                },
                context.trace_id,
            )

            # Execute
            logger.info(f"Step {step}: {agent.name} @ {context.stage.value}")
            context.log_step(f"{agent.name}")

            directive = TaskDirective(description="execute", priority="USER")
            result = agent.run(context, directive)

            context = result.context

            # Emit completion event
            EventBus.emit(
                Events.AGENT_COMPLETE,
                {
                    "agent": agent.name,
                    "status": result.status.name,
                    "message": result.message,
                },
                context.trace_id,
            )

            # Handle errors
            if result.status == AgentStatus.ERROR:
                EventBus.emit(
                    Events.AGENT_ERROR, {"message": result.message}, context.trace_id
                )
                logger.error(f"{agent.name} failed: {result.message}")
                break

            # Handle validation failure - REFLEXION LOOP
            if result.status == AgentStatus.VALIDATION_FAILED:
                if context.retry_count < self.MAX_RETRIES:
                    # Set reflexion feedback for retry
                    feedback = self._build_reflexion_prompt(result.message, context)
                    context.set_reflexion(feedback)

                    EventBus.emit(
                        Events.REFLEXION_TRIGGERED,
                        {"feedback": feedback, "retry_count": context.retry_count},
                        context.trace_id,
                    )

                    logger.warning(f"Reflexion triggered: {feedback}")
                    context.stage = ProcessingStage.SYNTHESIS  # Go back
                    continue
                else:
                    logger.error(f"Max retries ({self.MAX_RETRIES}) exceeded")
                    break

        if step >= self.max_steps:
            logger.warning("Max steps reached")

        logger.info(f"=== Workflow Ended: Stage={context.stage.value} ===")
        return context

    def _build_reflexion_prompt(self, error_msg: str, context: GlobalContext) -> str:
        """Build amended prompt for self-correction."""
        current_count = len(context.generated_content.faq_questions)
        needed = 15 - current_count

        return (
            f"You previously generated {current_count} questions. "
            f"The requirement is 15. Please generate {needed} more "
            f"to meet the threshold."
        )

    def _advance_stage_if_stuck(self, context: GlobalContext):
        """Advance stage if no worker handles it."""
        stage_order = [
            ProcessingStage.INGEST,
            ProcessingStage.SYNTHESIS,
            ProcessingStage.DRAFTING,
            ProcessingStage.VERIFICATION,
            ProcessingStage.COMPLETE,
        ]

        current_idx = stage_order.index(context.stage)
        if current_idx < len(stage_order) - 1:
            context.stage = stage_order[current_idx + 1]
            EventBus.emit(
                Events.STATE_CHANGE,
                {"new_stage": context.stage.value},
                context.trace_id,
            )
            logger.info(f"Advanced stage to {context.stage.value}")
