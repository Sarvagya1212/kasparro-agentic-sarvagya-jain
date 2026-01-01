"""
Orchestrator: Dynamic Agent Coordinator using Proposal System.
Agents propose actions - Coordinator selects the best proposal.
This demonstrates TRUE AGENT AUTONOMY - agents decide what to do.
"""

import logging
from typing import Dict, Optional

from .agents import BaseAgent
from .guardrails import Guardrails
from .memory import MemorySystem
from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    SystemState,
    TaskDirective,
    TaskPriority,
)
from .proposals import AgentProposal, EventBus, EventType, Event, ProposalSystem
from .state_manager import StateManager, WorkflowStatus

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Coordinator")


class Orchestrator(BaseAgent):
    """
    Dynamic Coordinator using Agent Proposals.

    Instead of deterministic routing, the Coordinator:
    1. Asks all agents what they can do (collect proposals)
    2. Selects the best proposal (highest confidence)
    3. Executes the selected agent

    This demonstrates TRUE AGENT AUTONOMY.
    """

    def __init__(self):
        super().__init__(
            name="Coordinator",
            role="Strategic Director",
            backstory="Strategic Director who orchestrates autonomous agents. "
            "Collects proposals from agents and selects the best course of action.",
        )
        self.agents: Dict[str, BaseAgent] = {}
        self.context = AgentContext()
        self.state = SystemState.IDLE
        self.max_steps = 20
        self._last_status: AgentStatus = None
        self._generation_complete: bool = False

        # State, Memory, and Proposal Systems
        self.state_manager = StateManager()
        self.memory = MemorySystem()
        self.proposal_system = ProposalSystem()
        self.event_bus = EventBus()

    def register_agent(self, agent: BaseAgent):
        """Register an agent for proposal-based coordination."""
        self.agents[agent.name] = agent
        self.proposal_system.register_agent(agent.name, agent)
        logger.info(f"Registered agent: {agent.name}")

    def determine_next_agent(self) -> Optional[str]:
        """
        Dynamic agent selection using proposals.
        Each agent proposes what it can do - we pick the best.
        """
        # Collect proposals from all agents
        proposals = self.proposal_system.collect_proposals(self.context)

        if not proposals:
            self.context.log_decision(
                "Coordinator",
                "No agent proposals available - workflow may be complete"
            )
            return None

        # Log all proposals for transparency
        self.context.log_decision(
            "Coordinator",
            f"Collected {len(proposals)} proposals from {len(self.agents)} agents"
        )

        for p in proposals:
            self.context.log_decision(
                "Coordinator",
                f"  → {p.agent_name}: {p.action} (confidence: {p.confidence:.2f}) - {p.reason}"
            )

        # Select best proposal
        best = self.proposal_system.select_best_proposal(
            proposals, strategy="priority_then_confidence"
        )

        if not best:
            self.context.log_decision(
                "Coordinator",
                "No valid proposals after filtering"
            )
            return None

        # Log the selection decision
        self.context.log_decision(
            "Coordinator",
            f"SELECTED: {best.agent_name} (confidence: {best.confidence:.2f}, "
            f"priority: {best.priority}) - {best.reason}"
        )

        # Publish event for agent selection
        self.event_bus.publish(Event(
            type="agent_selected",
            source="Coordinator",
            payload={"agent": best.agent_name, "confidence": best.confidence}
        ))

        return best.agent_name

    def run(self, initial_product_data=None):
        """Main execution loop with dynamic agent selection."""
        logger.info(f"Starting {self.name} ({self.role}) with DYNAMIC agent selection...")

        # Initialize state and memory
        self.state_manager.start_workflow()
        self.memory.start_session(
            "content_generation", {"initial_data": initial_product_data is not None}
        )

        self.context.log_decision(
            "Coordinator",
            "Initialized proposal-based coordination. Agents will propose actions."
        )

        step_count = 0

        # Root directive
        root_directive = TaskDirective(
            description="Process Product Data and Generate Content",
            priority=TaskPriority.SYSTEM,
        )

        # Apply input guardrails
        if initial_product_data:
            is_valid, error = Guardrails.before_model_callback(str(initial_product_data))
            if not is_valid:
                logger.error(f"Input blocked by guardrails: {error}")
                self.context.log_decision("Coordinator", f"BLOCKED: {error}")
                self.state = SystemState.ERROR
                self.state_manager.mark_error(error)
                return self.context

        while step_count < self.max_steps:
            # Dynamic agent selection via proposals
            next_agent_name = self.determine_next_agent()

            if not next_agent_name:
                logger.info("No agent proposals available. Workflow complete.")
                self.state = SystemState.COMPLETED
                break

            logger.info(f"Executing selected agent: {next_agent_name}")

            agent = self.agents.get(next_agent_name)
            if not agent:
                logger.error(f"Agent {next_agent_name} not found!")
                break

            # Execute with state tracking
            self.context.log_step(f"Running {next_agent_name}")
            state_space = self.state_manager.get_state()
            state_space.transition("execute", next_agent_name)

            # Checkpoint before execution
            self.state_manager.checkpoint()

            # Execute agent
            result = agent.run(self.context, root_directive)

            # Update context and status
            self.context = result.context
            self._last_status = result.status

            # Publish execution event
            self.event_bus.publish(Event(
                type=EventType.DATA_LOADED if next_agent_name == "DataAgent"
                else EventType.ANALYSIS_COMPLETE if next_agent_name == "AnalysisAgent"
                else EventType.GENERATION_COMPLETE if next_agent_name == "GenerationAgent"
                else "agent_complete",
                source=next_agent_name,
                payload={"status": result.status.value, "message": result.message}
            ))

            # Record in episodic memory
            self.memory.record_outcome(
                agent=next_agent_name,
                action="run",
                success=result.status not in [AgentStatus.ERROR, AgentStatus.VALIDATION_FAILED],
                context_summary=result.message,
            )

            # Handle result status
            logger.info(f"Agent {next_agent_name} finished: {result.status.value}")

            if result.status == AgentStatus.ERROR:
                logger.error(f"Critical error in {next_agent_name}: {result.message}")
                self.state = SystemState.ERROR
                self.state_manager.mark_error(result.message)
                break

            if result.status == AgentStatus.COMPLETE:
                if next_agent_name == "GenerationAgent":
                    self._generation_complete = True
                    state_space.mark_complete("generation")
                    logger.info("Generation complete. Checking for more proposals...")
                elif next_agent_name == "VerifierAgent":
                    self.state = SystemState.COMPLETED
                    self.state_manager.complete_workflow()
                    state_space.mark_complete("verification")
                    logger.info("System COMPLETED after verification.")
                    break

            step_count += 1

        if step_count >= self.max_steps:
            logger.warning("Max steps reached. Stopping to prevent infinite loop.")

        # Log final summary
        self.context.log_decision(
            "Coordinator",
            f"Workflow finished after {step_count} steps. "
            f"Final state: {self.state.value}"
        )

        # Log proposal statistics
        proposal_log = self.proposal_system.get_proposal_log()
        total_proposals = sum(p["proposals_count"] for p in proposal_log)
        self.context.log_decision(
            "Coordinator",
            f"Total proposals collected: {total_proposals} across {len(proposal_log)} rounds"
        )

        logger.info("Coordination finished.")
        return self.context
