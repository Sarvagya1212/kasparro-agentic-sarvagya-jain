"""
Orchestrator: Central Coordinator of the CWD System.
Implements strategic planning and oversight.
Routes to Delegator for execution and monitors overall progress.
Integrates Guardrails, Verifier, and Memory System for safety and state management.
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
from .state_manager import StateManager, WorkflowStatus

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Coordinator")


class Orchestrator(BaseAgent):
    """
    Coordinator Agent with State and Memory Management.
    Decides the high-level workflow:
    Data -> Synthetic (if needed) -> Delegator (Execution) -> Generation -> Verification
    """

    def __init__(self):
        super().__init__(
            name="Coordinator",
            role="Strategic Director",
            backstory="Strategic Director ensuring overall system integrity, "
            "optimizing flow, and managing high-level exceptions.",
        )
        self.agents: Dict[str, BaseAgent] = {}
        self.context = AgentContext()
        self.state = SystemState.IDLE
        self.max_steps = 20
        self._last_status: AgentStatus = None
        self._generation_complete: bool = False

        # State and Memory Management
        self.state_manager = StateManager()
        self.memory = MemorySystem()

    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator."""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def determine_next_agent(self) -> str:
        """
        High-level routing logic with state tracking.
        """
        state_space = self.state_manager.get_state()

        # 1. If we have no product data, start with DataAgent
        if not self.context.product_data:
            state_space.set_phase("data_loading", ["load_data", "generate_synthetic"])
            self.context.log_decision(
                "Coordinator", "Initial state: No data found. Starting DataAgent."
            )
            return "DataAgent"

        # 2. If product data exists but no comparison data
        if self.context.product_data and not self.context.comparison_data:
            if "SyntheticDataAgent" in self.agents:
                state_space.set_phase("data_augmentation", ["generate_synthetic"])
                self.context.log_decision(
                    "Coordinator", "No comparison data. Branching to SyntheticDataAgent."
                )
                return "SyntheticDataAgent"

        # 3. If data is present but not analyzed OR not validated
        if not self.context.analysis_results or not self.context.is_valid:
            if self._last_status == AgentStatus.VALIDATION_FAILED:
                logger.error("Delegator failed to validate after retries. Stopping.")
                return None

            state_space.set_phase("analysis", ["delegate", "validate"])
            self.context.log_decision(
                "Coordinator", "Data ready. Delegating execution to DelegatorAgent."
            )
            return "DelegatorAgent"

        # 4. If validated but not generated
        if self.context.is_valid and not self._generation_complete:
            state_space.set_phase("generation", ["generate_content"])
            self.context.log_decision(
                "Coordinator", "Validation passed. Routing to GenerationAgent."
            )
            return "GenerationAgent"

        # 5. After generation, run independent verification
        if self._generation_complete and "VerifierAgent" in self.agents:
            if (
                self._last_status != AgentStatus.COMPLETE
                or self.state != SystemState.COMPLETED
            ):
                state_space.set_phase("verification", ["verify"])
                self.context.log_decision(
                    "Coordinator",
                    "Generation complete. Routing to VerifierAgent for audit.",
                )
                return "VerifierAgent"

        return None

    def run(self, initial_product_data=None):
        """Main execution loop with state and memory management."""
        logger.info(f"Starting {self.name} ({self.role})...")

        # Initialize state and memory
        self.state_manager.start_workflow()
        self.memory.start_session(
            "content_generation", {"initial_data": initial_product_data is not None}
        )

        step_count = 0

        # Initial high-level directive
        root_directive = TaskDirective(
            description="Process Product Data and Generate Content",
            priority=TaskPriority.SYSTEM,
        )

        # Apply input guardrails if there's initial input
        if initial_product_data:
            is_valid, error = Guardrails.before_model_callback(str(initial_product_data))
            if not is_valid:
                logger.error(f"Input blocked by guardrails: {error}")
                self.context.log_decision("Coordinator", f"BLOCKED: {error}")
                self.state = SystemState.ERROR
                self.state_manager.mark_error(error)
                return self.context

        while step_count < self.max_steps:
            next_agent_name = self.determine_next_agent()

            if not next_agent_name:
                logger.info("No next agent determined. Workflow complete.")
                break

            logger.info(f"Routing to: {next_agent_name}")

            agent = self.agents.get(next_agent_name)
            if not agent:
                logger.error(f"Agent {next_agent_name} not found!")
                break

            # Execute Agent with state tracking
            self.context.log_step(f"Running {next_agent_name}")
            state_space = self.state_manager.get_state()
            state_space.transition("execute", next_agent_name)

            # Checkpoint before execution
            self.state_manager.checkpoint()

            # Pass directive down
            result = agent.run(self.context, root_directive)

            # Update Context and track status
            self.context = result.context
            self._last_status = result.status

            # Record outcome in episodic memory
            self.memory.record_outcome(
                agent=next_agent_name,
                action="run",
                success=result.status
                not in [AgentStatus.ERROR, AgentStatus.VALIDATION_FAILED],
                context_summary=result.message,
            )

            # Handle Result Status
            logger.info(
                f"Agent {next_agent_name} finished with status: {result.status.value}"
            )

            if result.status == AgentStatus.ERROR:
                logger.error(f"Critical error in {next_agent_name}: {result.message}")
                self.state = SystemState.ERROR
                self.state_manager.mark_error(result.message)
                break

            if result.status == AgentStatus.COMPLETE:
                if next_agent_name == "GenerationAgent":
                    self._generation_complete = True
                    state_space.mark_complete("generation")
                    logger.info("Generation complete. Proceeding to verification.")
                elif next_agent_name == "VerifierAgent":
                    self.state = SystemState.COMPLETED
                    self.state_manager.complete_workflow()
                    state_space.mark_complete("verification")
                    logger.info("System marked as COMPLETED after verification.")
                    break

            step_count += 1

        if step_count >= self.max_steps:
            logger.warning("Max steps reached. Stopping to prevent infinite loop.")

        logger.info("Coordination finished.")
        return self.context
