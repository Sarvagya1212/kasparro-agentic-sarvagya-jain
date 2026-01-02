"""
Priority Router - Simple stage-based agent routing.
No complex bidding, just can_handle() boolean checks.
"""

import logging
from typing import List, Optional

from skincare_agent_system.core.models import GlobalContext


logger = logging.getLogger("Router")


class PriorityRouter:
    """
    Simple priority-based router.
    Agents return can_handle(state) boolean, router picks first match.
    """

    def __init__(self, agents: List):
        self.agents = agents
        logger.info(f"PriorityRouter initialized with {len(agents)} agents")

    def select_next(self, context: GlobalContext) -> Optional[object]:
        """
        Select next agent based on can_handle boolean.
        Returns the agent object (not a proposal).
        """
        for agent in self.agents:
            if hasattr(agent, "can_handle"):
                if agent.can_handle(context):
                    logger.info(f"Selected: {agent.name} (stage={context.stage.value})")
                    return agent

        logger.info("No agent can handle current state")
        return None


class Rejection:
    """
    Rejection object - returned when validation fails.
    Triggers re-run of specified worker.
    """

    def __init__(self, reason: str, retry_worker: str = None):
        self.reason = reason
        self.retry_worker = retry_worker

    def __repr__(self):
        return f"Rejection({self.reason}, retry={self.retry_worker})"
