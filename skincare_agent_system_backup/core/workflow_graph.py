"""
LangGraph Workflow Definition.
Formalizes the Coordinator-Worker-Delegator pattern as a State Machine.
"""

import logging
import operator
from typing import Annotated, Dict, List, Literal, Optional, TypedDict, Union

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from skincare_agent_system.actors.agent_implementations import (
    DataAgent,
    GenerationAgent,
)
from skincare_agent_system.actors.delegator import DelegatorAgent
from skincare_agent_system.actors.verifier import VerifierAgent
from skincare_agent_system.core.models import AgentContext, AgentStatus

logger = logging.getLogger("WorkflowGraph")


class AgentState(TypedDict):
    """
    Graph state that wraps the AgentContext.
    LangGraph requires a TypedDict state.
    """

    context: AgentContext
    next_agent: Optional[str]
    messages: Annotated[List[BaseMessage], operator.add]
    steps_count: int
    workflow_status: str


def create_workflow_graph(
    orchestrator: Orchestrator,
    agents: Dict[str, Union[DataAgent, DelegatorAgent, GenerationAgent, VerifierAgent]],
):
    """
    Constructs the LangGraph state machine.
    """

    # --- NODES ---

    def coordinator_node(state: AgentState):
        """
        Coordinator node: Determines the next step using ProposalSystem.
        """
        logger.info("--- COORDINATOR ---")
        orchestrator.context = state["context"]

        # Collect proposals
        next_agent = orchestrator.determine_next_agent()

        step_count = state["steps_count"] + 1
        return {
            "next_agent": next_agent,
            "steps_count": step_count,
            "workflow_status": "active",
        }

    def data_node(state: AgentState):
        logger.info("--- DATA AGENT ---")
        agent = agents["DataAgent"]
        result = agent.run(state["context"])
        return {"context": result.context}

    def delegator_node(state: AgentState):
        logger.info("--- DELEGATOR (ANALYSIS) ---")
        agent = agents["DelegatorAgent"]
        result = agent.run(state["context"])
        return {"context": result.context}

    def generation_node(state: AgentState):
        logger.info("--- GENERATION ---")
        agent = agents["GenerationAgent"]
        result = agent.run(state["context"])
        return {"context": result.context}

    def verifier_node(state: AgentState):
        logger.info("--- VERIFIER ---")
        agent = agents["VerifierAgent"]
        result = agent.run(state["context"])

        status = "completed" if result.status == AgentStatus.COMPLETE else "failed"
        return {"context": result.context, "workflow_status": status}

    # --- ROUTING LOGIC ---

    def route_next(
        state: AgentState,
    ) -> Literal[
        "DataAgent",
        "SyntheticDataAgent",
        "DelegatorAgent",
        "GenerationAgent",
        "VerifierAgent",
        "__end__",
    ]:
        """
        DYNAMIC conditional edge routing based on proposals and context state.

        Instead of hardcoded routing, this function:
        1. Checks the proposal-selected next_agent
        2. Validates against current context state
        3. Applies fallback rules for edge cases
        """
        next_agent = state["next_agent"]
        context = state["context"]
        steps = state["steps_count"]

        # Termination conditions
        if not next_agent:
            logger.info("No agent proposed - workflow complete")
            return END

        if steps > 15:
            logger.warning(f"Max steps ({steps}) exceeded - forcing termination")
            return END

        # Context-based routing overrides
        if context.is_valid and state.get("workflow_status") == "completed":
            logger.info("Workflow marked complete - terminating")
            return END

        # Dynamic routing based on proposal with validation
        valid_agents = [
            "DataAgent",
            "SyntheticDataAgent",
            "DelegatorAgent",
            "GenerationAgent",
            "VerifierAgent",
        ]

        if next_agent in valid_agents:
            # Context-aware validation before routing
            if next_agent == "GenerationAgent" and not context.is_valid:
                logger.warning(
                    "GenerationAgent proposed but context not valid "
                    "- rerouting to DelegatorAgent"
                )
                return "DelegatorAgent"

            if next_agent == "VerifierAgent" and not context.is_valid:
                logger.warning(
                    "VerifierAgent proposed but context not valid "
                    "- rerouting to DelegatorAgent"
                )
                return "DelegatorAgent"

            logger.info(f"Dynamic routing to: {next_agent}")
            return next_agent

        # Fallback: Check context state for implicit routing
        if context.product_data is None:
            return "DataAgent"
        if context.comparison_data is None:
            return "SyntheticDataAgent"
        if not context.is_valid:
            return "DelegatorAgent"

        logger.info("Fallback: No valid route - ending workflow")
        return END

    # --- GRAPH CONSTRUCTION ---

    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("Coordinator", coordinator_node)
    workflow.add_node("DataAgent", data_node)
    workflow.add_node("DelegatorAgent", delegator_node)
    workflow.add_node("GenerationAgent", generation_node)
    workflow.add_node("VerifierAgent", verifier_node)
    # Note: SyntheticDataAgent mapping is missing in simplistic Logic above.
    # Adding generic node wrapper would be better, but strict nodes are clearer.
    # Let's add Synthetic node.

    def synthetic_node(state: AgentState):
        logger.info("--- SYNTHETIC DATA ---")
        agent = agents.get("SyntheticDataAgent")
        if agent:
            result = agent.run(state["context"])
            return {"context": result.context}
        return {}

    workflow.add_node("SyntheticDataAgent", synthetic_node)

    # Set Entry Point
    workflow.set_entry_point("Coordinator")

    # Add Edges
    # Coordinator -> [Conditional] -> Agents
    workflow.add_conditional_edges("Coordinator", route_next)

    # Agents -> Coordinator (Loop back for next proposal)
    workflow.add_edge("DataAgent", "Coordinator")
    workflow.add_edge("SyntheticDataAgent", "Coordinator")
    workflow.add_edge("DelegatorAgent", "Coordinator")
    workflow.add_edge("GenerationAgent", "Coordinator")

    # Verifier -> End (or Coordinator if iterative? Usually Verifier is last)
    # But Verifier might fail and require retry?
    # Current logic: Verifier -> COMPLETED -> break.
    # So we can edge to END or Coordinator (which will see COMPLETED and return None).
    # Let's loop back to Coordinator to let it decide "No more proposals".
    workflow.add_edge("VerifierAgent", "Coordinator")

    return workflow.compile()
