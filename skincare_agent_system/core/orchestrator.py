"""
Orchestrator: Stage-based routing with can_handle checks.
Simple priority router - no complex bidding.
"""

import logging
from typing import Dict, List, Optional

from skincare_agent_system.core.models import (
    GlobalContext,
    AgentStatus,
    ProcessingStage,
    TaskDirective,
)
from skincare_agent_system.core.proposals import PriorityRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Orchestrator")


class SimpleMemory:
    """Simple execution history."""
    def __init__(self):
        self.execution_history: List[str] = []

    def log(self, action: str):
        self.execution_history.append(action)


class Orchestrator:
    """
    Stage-based orchestrator using can_handle routing.
    No complex bidding - just boolean checks.
    """

    def __init__(self, max_steps: int = 20):
        self.agents: Dict[str, object] = {}
        self.max_steps = max_steps
        self.memory = SimpleMemory()
        self.router: Optional[PriorityRouter] = None

    def register_agent(self, agent: object):
        """Add agent to pool."""
        self.agents[agent.name] = agent
        logger.info(f"Registered: {agent.name}")

    def run(self, context: GlobalContext) -> GlobalContext:
        """
        Main loop: Check can_handle → Execute → Advance stage.
        """
        logger.info("=== Starting Stage-Based Orchestration ===")
        
        if not self.agents:
            raise ValueError("No agents registered")
        
        self.router = PriorityRouter(list(self.agents.values()))
        
        step = 0
        while step < self.max_steps:
            step += 1
            
            # Check if complete
            if context.stage == ProcessingStage.COMPLETE:
                logger.info("Stage=COMPLETE. Done.")
                break
            
            # Find agent that can_handle current state
            agent = self.router.select_next(context)
            
            if not agent:
                # No agent can handle - advance stage manually
                self._advance_stage_if_stuck(context)
                continue
            
            # Execute
            logger.info(f"Step {step}: {agent.name} @ {context.stage.value}")
            context.log_step(f"{agent.name}")
            
            directive = TaskDirective(description="execute", priority='USER')
            result = agent.run(context, directive)
            
            context = result.context
            self.memory.log(f"{agent.name}: {result.status.name}")
            
            # Handle errors
            if result.status == AgentStatus.ERROR:
                logger.error(f"{agent.name} failed: {result.message}")
                break
            
            # Handle validation failure - retry questions
            if result.status == AgentStatus.VALIDATION_FAILED:
                logger.warning(f"Validation failed: {result.message}")
                context.stage = ProcessingStage.SYNTHESIS  # Go back to regenerate
                continue

        if step >= self.max_steps:
            logger.warning("Max steps reached")

        logger.info(f"=== Workflow Ended: Stage={context.stage.value} ===")
        return context

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
            logger.info(f"Advanced stage to {context.stage.value}")
