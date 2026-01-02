"""
Simplified Agent Action Proposals.
Agents propose actions, and a simple selector chooses the best one.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


from skincare_agent_system.core.models import GlobalContext


logger = logging.getLogger("Proposals")


@dataclass
class AgentProposal:
    """
    A proposal from an agent about what it can do.
    """
    agent_name: str
    action: str
    confidence: float
    reason: str
    preconditions_met: bool
    priority: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __repr__(self):
        status = "✓" if self.preconditions_met else "✗"
        return (
            f"[{status}] {self.agent_name}: {self.action} "
            f"(confidence: {self.confidence:.2f}, priority: {self.priority}) - {self.reason}"
        )


class SimpleProposalSystem:
    """
    A simple, priority-based proposal selection system.
    """

    def __init__(self, agents: List[Any]):
        self.agents = agents
        logger.info(f"SimpleProposalSystem initialized with {len(self.agents)} agents.")

    def select_next(self, context: GlobalContext) -> Optional[AgentProposal]:
        """
        Collects proposals and selects the best one based on priority and confidence.
        """
        proposals = []
        for agent in self.agents:
            try:
                if hasattr(agent, "propose"):
                    proposal = agent.propose(context)
                    if proposal:
                        proposals.append(proposal)
            except Exception as e:
                logger.warning(f"Agent {agent.name} failed to propose: {e}")
        
        if not proposals:
            logger.warning("No proposals received from any agent.")
            return None

        # Filter for valid proposals where preconditions are met
        valid_proposals = [p for p in proposals if p.preconditions_met and p.confidence > 0]

        if not valid_proposals:
            logger.info("No valid proposals with met preconditions.")
            return None

        # Select the best proposal based on highest priority, then highest confidence
        best_proposal = max(valid_proposals, key=lambda p: (p.priority, p.confidence))
        
        logger.info(f"Selected proposal: {best_proposal.agent_name} -> {best_proposal.action}")
        return best_proposal
