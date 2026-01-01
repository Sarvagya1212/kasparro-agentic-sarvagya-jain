"""
Orchestrator: Central Coordinator of the CWD System.
Implements strategic planning and oversight.
Routes to Delegator for execution and monitors overall progress.
Integrates Guardrails and Verifier for safety.
"""

import logging
from typing import Dict, Optional

from .agents import BaseAgent
from .guardrails import Guardrails
from .models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    SystemState,
    TaskDirective,
    TaskPriority,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Coordinator")


class Orchestrator(BaseAgent):
    """
    Coordinator Agent.
    Decides the high-level workflow:
    Data -> Synthetic (if needed) -> Delegator (Execution) -> Generation -> Verification
    """

    def __init__(self):
        super().__init__(
            name="Coordinator",
            role="Strategic Director",
            backstory="Strategic Director ensuring the overall system integrity, optimizing flow, and managing high-level exceptions.",
        )
        self.agents: Dict[str, BaseAgent] = {}
        self.context = AgentContext()
        self.state = SystemState.IDLE
        self.max_steps = 20
        self._last_status: AgentStatus = None
        self._generation_complete: bool = False  # Track if generation has run

    def register_agent(self, agent: BaseAgent):
        """Register an agent with the orchestrator."""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def determine_next_agent(self) -> str:
        """
        High-level routing logic.
        """
        # 1. If we have no product data, start with DataAgent
        if not self.context.product_data:
            self.context.log_decision(
                "Coordinator", "Initial state: No data found. Starting DataAgent."
            )
            return "DataAgent"

        # 2. If product data exists but no comparison data, branch to SyntheticDataAgent
        if self.context.product_data and not self.context.comparison_data:
            if "SyntheticDataAgent" in self.agents:
                self.context.log_decision(
                    "Coordinator",
                    "No comparison data. Branching to SyntheticDataAgent.",
                )
                return "SyntheticDataAgent"

        # 3. If data is present but not analyzed OR not validated, Delegate
        if not self.context.analysis_results or not self.context.is_valid:
            if self._last_status == AgentStatus.VALIDATION_FAILED:
                logger.error("Delegator failed to validate after retries. Stopping.")
                return None

            self.context.log_decision(
                "Coordinator", "Data ready. Delegating execution to DelegatorAgent."
            )
            return "DelegatorAgent"

        # 4. If validated but not generated, Generate
        if self.context.is_valid and not self._generation_complete:
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
                self.context.log_decision(
                    "Coordinator",
                    "Generation complete. Routing to VerifierAgent for independent audit.",
                )
                return "VerifierAgent"

        return None

    def run(self, initial_product_data=None):
        """Main execution loop with guardrails integration."""
        logger.info(f"Starting {self.name} ({self.role})...")

        step_count = 0

        # Initial high-level directive
        root_directive = TaskDirective(
            description="Process Product Data and Generate Content",
            priority=TaskPriority.SYSTEM,
        )

        # Apply input guardrails if there's initial input
        if initial_product_data:
            is_valid, error = Guardrails.before_model_callback(
                str(initial_product_data)
            )
            if not is_valid:
                logger.error(f"Input blocked by guardrails: {error}")
                self.context.log_decision("Coordinator", f"BLOCKED: {error}")
                self.state = SystemState.ERROR
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

            # Execute Agent
            self.context.log_step(f"Running {next_agent_name}")

            # Pass directive down
            result = agent.run(self.context, root_directive)

            # Update Context and track status
            self.context = result.context
            self._last_status = result.status

            # Handle Result Status
            logger.info(
                f"Agent {next_agent_name} finished with status: {result.status.value}"
            )

            if result.status == AgentStatus.ERROR:
                logger.error(f"Critical error in {next_agent_name}: {result.message}")
                self.state = SystemState.ERROR
                break

            if result.status == AgentStatus.COMPLETE:
                if next_agent_name == "GenerationAgent":
                    self._generation_complete = True
                    logger.info("Generation complete. Proceeding to verification.")
                elif next_agent_name == "VerifierAgent":
                    self.state = SystemState.COMPLETED
                    logger.info("System marked as COMPLETED after verification.")
                    break

            step_count += 1

        if step_count >= self.max_steps:
            logger.warning("Max steps reached. Stopping to prevent infinite loop.")

        logger.info("Coordination finished.")
        return self.context
