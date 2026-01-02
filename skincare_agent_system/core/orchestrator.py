"""
Orchestrator: Dynamic Agent Coordinator using Proposal System.
Agents propose actions - Coordinator selects the best proposal.
This demonstrates TRUE AGENT AUTONOMY - agents decide what to do.
"""

import logging
from typing import Dict, Optional

from skincare_agent_system.actors.agents import BaseAgent
from skincare_agent_system.cognition.memory import MemorySystem
from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    SystemState,
    TaskDirective,
    TaskPriority,
)
from skincare_agent_system.core.proposals import (
    AgentProposal,
    Event,
    EventBus,
    EventType,
    Goal,
    GoalManager,
    ProposalSystem,
)
from skincare_agent_system.core.state_manager import StateManager, WorkflowStatus
from skincare_agent_system.infrastructure.tracer import get_tracer
from skincare_agent_system.security.guardrails import Guardrails

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

        # PHASE 2: Persistent GoalManager (single instance)
        self.goal_manager = GoalManager()

        # FIX: Active coalition tracking for complex tasks
        self._active_coalition = None

        self._initialize_default_goals()

    def _estimate_task_complexity(self) -> float:
        """
        FIX: Estimate current task complexity for coalition formation.
        Returns value 0.0-1.0 where >0.6 triggers coalition.
        """
        complexity = 0.3  # Base complexity

        # Increase complexity based on workflow state
        if self.context.product_data is None:
            complexity += 0.1  # Need data loading
        if self.context.comparison_data is None:
            complexity += 0.1  # Need synthetic data
        if not self.context.is_valid:
            complexity += 0.2  # Need validation
        if len(self.context.validation_errors) > 0:
            complexity += 0.1 * min(3, len(self.context.validation_errors))

        return min(1.0, complexity)

    def _initialize_default_goals(self):
        """Initialize default goals. Can be overridden by dynamic goal derivation."""
        self.goal_manager.add_goal(
            Goal(
                id="load_data",
                description="Load product and comparison data",
                success_criteria=["product_data_loaded", "comparison_data_loaded"],
            )
        )
        self.goal_manager.add_goal(
            Goal(
                id="analyze",
                description="Complete product analysis",
                success_criteria=["analysis_complete", "validation_passed"],
            )
        )
        self.goal_manager.add_goal(
            Goal(
                id="generate",
                description="Generate content pages",
                success_criteria=["content_generated"],
            )
        )
        logger.info(
            f"GoalManager initialized with {len(self.goal_manager._goals)} default goals"
        )

    def derive_goals_from_context(self, input_context: dict = None):
        """
        PHASE 2: Dynamically derive goals from input context.
        Allows customization of goals based on specific requirements.
        """
        if not input_context:
            return

        # Example: Add custom goals based on input
        if input_context.get("require_comparison"):
            self.goal_manager.add_goal(
                Goal(
                    id="comparison_analysis",
                    description="Generate detailed product comparison",
                    success_criteria=[
                        "comparison_data_loaded",
                        "comparison_analysis_complete",
                    ],
                    priority=2,
                )
            )

        if input_context.get("min_faqs"):
            self.goal_manager.add_goal(
                Goal(
                    id="faq_generation",
                    description=f"Generate minimum {input_context['min_faqs']} FAQs",
                    success_criteria=["faq_count_met"],
                    priority=3,
                )
            )

        logger.info(
            f"Derived additional goals from context. Total: {len(self.goal_manager._goals)}"
        )

    def register_agent(self, agent: BaseAgent):
        """Register an agent for proposal-based coordination and event publishing."""
        self.agents[agent.name] = agent
        self.proposal_system.register_agent(agent.name, agent)

        # Connect agent to event bus for pub/sub communication
        agent.set_event_bus(self.event_bus)

        # PHASE 3: Pass memory reference for memory-influenced proposals
        agent.set_memory(self.memory)

        # PHASE 2: Pass goal manager for subgoal proposals
        agent.set_goal_manager(self.goal_manager)

        logger.info(
            f"Registered agent: {agent.name} (event bus, memory, goals connected)"
        )

    def determine_next_agent(self) -> Optional[str]:
        """
        Dynamic agent selection using proposals + negotiation.
        FIX: Now includes multi-round negotiation before selection.
        """
        # Collect proposals from all agents
        proposals = self.proposal_system.collect_proposals(self.context)

        if not proposals:
            self.context.log_decision(
                "Coordinator", "No agent proposals available - workflow may be complete"
            )
            return None

        # Log all proposals for transparency
        self.context.log_decision(
            "Coordinator",
            f"Collected {len(proposals)} proposals from {len(self.agents)} agents",
        )

        for p in proposals:
            self.context.log_decision(
                "Coordinator",
                f"  → {p.agent_name}: {p.action} (confidence: {p.confidence:.2f}) - {p.reason}",
            )

        # FIX: Apply negotiation protocol for multiple competing proposals
        if len(proposals) > 1:
            negotiated = self.proposal_system.negotiate_proposals(
                proposals, max_rounds=3
            )
            self.context.log_decision(
                "Coordinator",
                f"Negotiation: {len(proposals)} -> {len(negotiated)} proposals after adjustment",
            )
            proposals = negotiated

        # FIX: Check for coalition formation on complex tasks
        task_complexity = self._estimate_task_complexity()
        coalition = self.proposal_system.form_coalition(proposals, task_complexity)
        if coalition:
            self.context.log_decision(
                "Coordinator",
                f"Coalition formed: {coalition['members']} (strength: {coalition['combined_confidence']:.2f})",
            )
            # Execute coalition leader, store coalition for later
            self._active_coalition = coalition

        # Select best proposal
        best = self.proposal_system.select_best_proposal(
            proposals, strategy="priority_then_confidence"
        )

        if not best:
            self.context.log_decision(
                "Coordinator", "No valid proposals after filtering"
            )
            return None

        # Log the selection decision
        self.context.log_decision(
            "Coordinator",
            f"SELECTED: {best.agent_name} (confidence: {best.confidence:.2f}, "
            f"priority: {best.priority}) - {best.reason}",
        )

        # Publish event for agent selection
        self.event_bus.publish(
            Event(
                type="agent_selected",
                source="Coordinator",
                payload={"agent": best.agent_name, "confidence": best.confidence},
            )
        )

        return best.agent_name

    def run(self, initial_product_data=None):
        """Main execution loop with dynamic agent selection."""
        logger.info(
            f"Starting {self.name} ({self.role}) with DYNAMIC agent selection..."
        )

        # Initialize state and memory
        self.state_manager.start_workflow()
        self.memory.start_session(
            "content_generation", {"initial_data": initial_product_data is not None}
        )

        # Start Trace
        tracer = get_tracer()
        trace_id = tracer.start_trace("content_generation_workflow")
        self.context.log_decision("Coordinator", f"Started execution trace: {trace_id}")

        self.context.log_decision(
            "Coordinator",
            "Initialized proposal-based coordination. Agents will propose actions.",
        )

        step_count = 0

        # Root directive
        root_directive = TaskDirective(
            description="Process Product Data and Generate Content",
            priority=TaskPriority.SYSTEM,
        )

        # Apply input guardrails
        if initial_product_data:
            is_valid, error = Guardrails.before_model_callback(
                str(initial_product_data)
            )
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
            self.event_bus.publish(
                Event(
                    type=(
                        EventType.DATA_LOADED
                        if next_agent_name == "DataAgent"
                        else (
                            EventType.ANALYSIS_COMPLETE
                            if next_agent_name == "AnalysisAgent"
                            else (
                                EventType.GENERATION_COMPLETE
                                if next_agent_name == "GenerationAgent"
                                else "agent_complete"
                            )
                        )
                    ),
                    source=next_agent_name,
                    payload={"status": result.status.value, "message": result.message},
                )
            )

            # Record in episodic memory
            self.memory.record_outcome(
                agent=next_agent_name,
                action="run",
                success=result.status
                not in [AgentStatus.ERROR, AgentStatus.VALIDATION_FAILED],
                context_summary=result.message,
            )

            # Handle result status
            logger.info(f"Agent {next_agent_name} finished: {result.status.value}")

            if result.status == AgentStatus.ERROR:
                logger.error(f"Critical error in {next_agent_name}: {result.message}")
                self.state = SystemState.ERROR
                self.state_manager.mark_error(result.message)
                tracer.end_trace(status="failed")
                break

            # Check goal completion (GOAL-DRIVEN TERMINATION)
            if result.status == AgentStatus.COMPLETE:
                # PHASE 2: Use PERSISTENT goal_manager (not new instance each cycle)
                # Check if all goals achieved
                if self.goal_manager.all_goals_achieved(self.context):
                    self.state = SystemState.COMPLETED
                    self.state_manager.complete_workflow()
                    logger.info("All goals achieved. Workflow COMPLETED.")
                    tracer.end_trace(status="completed")
                    tracer.export_trace()
                    break

            step_count += 1

        if step_count >= self.max_steps:
            logger.warning("Max steps reached. Stopping to prevent infinite loop.")

        # Log final summary
        self.context.log_decision(
            "Coordinator",
            f"Workflow finished after {step_count} steps. "
            f"Final state: {self.state.value}",
        )

        # Log proposal statistics
        proposal_log = self.proposal_system.get_proposal_log()
        total_proposals = sum(p["proposals_count"] for p in proposal_log)
        self.context.log_decision(
            "Coordinator",
            f"Total proposals collected: {total_proposals} across {len(proposal_log)} rounds",
        )

        logger.info("Coordination finished.")
        return self.context
