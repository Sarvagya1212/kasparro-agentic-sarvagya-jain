"""
Orchestrator: Simplified Agent Coordinator using Blackboard pattern.
Broadcast → Bid → Select → Execute loop.
"""

import logging
from typing import Dict, List, Optional

from skincare_agent_system.core.models import (
    GlobalContext,
    AgentStatus,
    ProcessingStage,
    TaskDirective,
)
from skincare_agent_system.core.proposals import SimpleProposalSystem, AgentProposal

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Orchestrator")


class SimpleMemory:
    """Simple execution history log."""
    def __init__(self):
        self.execution_history: List[str] = []

    def log(self, action: str):
        self.execution_history.append(action)
        logger.info(f"Memory: {action}")

    def recent(self, n: int = 5) -> List[str]:
        return self.execution_history[-n:]


class Orchestrator:
    """
    Blackboard-style orchestrator.
    Agents observe shared GlobalContext and bid for execution.
    """

    def __init__(self, max_steps: int = 20):
        self.agents: Dict[str, object] = {}
        self.max_steps = max_steps
        self.memory = SimpleMemory()
        self.proposal_system: Optional[SimpleProposalSystem] = None

    def register_agent(self, agent: object):
        """Add an agent to the pool."""
        self.agents[agent.name] = agent
        logger.info(f"Registered: {agent.name}")

    def run(self, context: GlobalContext) -> GlobalContext:
        """
        Main orchestration loop: Broadcast → Bid → Select → Execute.
        
        Args:
            context: GlobalContext with product_input already loaded
            
        Returns:
            Updated GlobalContext after all agents have run
        """
        logger.info("=== Starting Blackboard Orchestration ===")
        
        # Initialize proposal system with registered agents
        if not self.agents:
            raise ValueError("No agents registered")
        self.proposal_system = SimpleProposalSystem(list(self.agents.values()))
        
        step = 0
        while step < self.max_steps:
            step += 1
            logger.info(f"--- Step {step} ---")
            
            # 1. BROADCAST: All agents see current state via propose()
            # 2. BID: Collect proposals
            # 3. SELECT: Pick best proposal
            best_proposal = self.proposal_system.select_next(context)
            
            if not best_proposal:
                logger.info("No valid proposals. Workflow complete.")
                break
            
            # 4. EXECUTE: Run winning agent
            agent_name = best_proposal.agent_name
            agent = self.agents.get(agent_name)
            
            if not agent:
                logger.error(f"Agent '{agent_name}' not found")
                break
            
            context.log_step(f"{agent_name}: {best_proposal.action}")
            
            directive = TaskDirective(description=best_proposal.action, priority='USER')
            result = agent.run(context, directive)
            
            # Update context from result
            context = result.context
            self.memory.log(f"{agent_name}: {result.status.name}")
            
            if result.status == AgentStatus.ERROR:
                logger.error(f"{agent_name} failed: {result.message}")
                break
            
            # Check if complete
            if context.stage == ProcessingStage.COMPLETE:
                logger.info("Stage=COMPLETE. Workflow finished.")
                break

        if step >= self.max_steps:
            logger.warning("Max steps reached.")

        logger.info(f"=== Workflow Ended: Stage={context.stage.value} ===")
        return context
