"""
Orchestrator: Dynamic Agent Coordinator using Proposal System.
Simplified for Phase 1.
"""

import logging
from typing import Dict, Optional

from skincare_agent_system.actors.base_agent import BaseAgent
from skincare_agent_system.core.models import (
    AgentContext,
    AgentStatus,
    SystemState,
    TaskDirective,
    TaskPriority,
)
from skincare_agent_system.core.proposals import (
    Event,
    EventBus,
    EventType,
    Goal,
    GoalManager,
    ProposalSystem,
)
from skincare_agent_system.core.state_manager import StateManager
from skincare_agent_system.infrastructure.logger import get_logger

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Coordinator")
system_log = get_logger("Orchestrator")


# Stub classes for missing dependencies
class MockMemory:
    def start_session(self, *args, **kwargs):
        pass

    def record_outcome(self, *args, **kwargs):
        pass


class MockTracer:
    def start_trace(self, *args, **kwargs):
        return "trace_id"

    def end_trace(self, *args, **kwargs):
        pass

    def export_trace(self, *args, **kwargs):
        pass


class Orchestrator(BaseAgent):
    """
    Dynamic Coordinator using Agent Proposals.
    """

    def __init__(self):
        super().__init__(
            name="Coordinator",
            role="Strategic Director",
            backstory="Strategic Director who orchestrates autonomous agents.",
        )
        self.agents: Dict[str, BaseAgent] = {}
        self.context = AgentContext()
        self.state = SystemState.IDLE
        self.max_steps = 20
        self._last_status: AgentStatus = None
        self._generation_complete: bool = False

        self.state_manager = StateManager()
        self.memory = MockMemory()  # Stub
        self.proposal_system = ProposalSystem()
        self.event_bus = EventBus()
        self.goal_manager = GoalManager()

        self._active_coalition = None
        self._initialize_default_goals()

    def _estimate_task_complexity(self) -> float:
        complexity = 0.3
        if self.context.product_data is None:
            complexity += 0.1
        if self.context.comparison_data is None:
            complexity += 0.1
        if not self.context.is_valid:
            complexity += 0.2
        if len(self.context.validation_errors) > 0:
            complexity += 0.1 * min(3, len(self.context.validation_errors))
        return min(1.0, complexity)

    def _initialize_default_goals(self):
        self.goal_manager.add_goal(
            Goal(
                id="load_data",
                description="Load product data",
                success_criteria=["product_data_loaded"],
            )
        )
        self.goal_manager.add_goal(
            Goal(
                id="analyze",
                description="Analysis",
                success_criteria=["analysis_complete"],
            )
        )
        self.goal_manager.add_goal(
            Goal(
                id="generate",
                description="Generate content",
                success_criteria=["content_generated"],
            )
        )

    def derive_goals_from_context(self, input_context: dict = None):
        if not input_context:
            return
        if input_context.get("require_comparison"):
            self.goal_manager.add_goal(
                Goal(
                    id="comp",
                    description="Comparison",
                    success_criteria=["comparison_complete"],
                )
            )

    def register_agent(self, agent: BaseAgent):
        self.agents[agent.name] = agent
        self.proposal_system.register_agent(agent.name, agent)
        agent.set_event_bus(self.event_bus)
        # agent.set_memory(self.memory) # BaseAgent stub
        # agent.set_goal_manager(self.goal_manager) # BaseAgent stub

    def determine_next_agent(self) -> Optional[str]:
        # Simple proposal selection for simplified version
        proposals = self.proposal_system.collect_proposals(self.context)
        if not proposals:
            return None

        # Just pick best confidence
        best = self.proposal_system.select_best_proposal(proposals)
        if best:
            return best.agent_name
        return None

    def execute_proposal(self, agent_name: str, directive: TaskDirective):
        """
        Execute an agent with robust error handling.
        Catches exceptions and returns proper AgentResult on failure.
        """
        import traceback
        from skincare_agent_system.core.models import AgentResult

        try:
            agent = self.agents.get(agent_name)
            if not agent:
                logger.error(f"✗ Agent {agent_name} not found")
                return AgentResult(
                    agent_name=agent_name,
                    status=AgentStatus.ERROR,
                    context=self.context,
                    message=f"Agent {agent_name} not registered"
                )

            result = agent.run(self.context, directive)

            # Validate result type
            if not isinstance(result, AgentResult):
                logger.error(f"✗ Agent {agent_name} returned invalid type: {type(result)}")
                return AgentResult(
                    agent_name=agent_name,
                    status=AgentStatus.ERROR,
                    context=self.context,
                    message=f"Invalid result type: {type(result)}"
                )

            if result.status == AgentStatus.ERROR:
                logger.error(f"✗ Agent {agent_name} failed: {result.message}")
            else:
                logger.info(f"✓ {agent_name} executed successfully")

            return result

        except Exception as e:
            logger.error(f"✗ Execution error in {agent_name}: {e}\n{traceback.format_exc()}")
            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.ERROR,
                context=self.context,
                message=str(e)
            )

    def execute_with_retry(self, agent_name: str, directive: TaskDirective, max_retries: int = 3):
        """
        Execute proposal with exponential backoff retry.
        """
        import time
        from skincare_agent_system.core.models import AgentResult

        for attempt in range(max_retries):
            result = self.execute_proposal(agent_name, directive)

            if result.status != AgentStatus.ERROR:
                return result

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(f"Retry {attempt + 1}/{max_retries} for {agent_name} in {wait_time}s")
                time.sleep(wait_time)

        logger.error(f"Agent {agent_name} failed after {max_retries} retries")
        return result


    def run(self, initial_product_data=None):
        system_log.info("=== Starting workflow ===", extra={"type": "workflow_start"})
        logger.info(f"Starting {self.name}...")
        self.state_manager.start_workflow()

        # Load initial data if provided
        if initial_product_data:
            from skincare_agent_system.core.models import ProductData

            try:
                if isinstance(initial_product_data, dict):
                    self.context.product_data = ProductData(**initial_product_data)
                    self.context.log_decision(
                        "System", "Initial product data loaded safely"
                    )
            except Exception as e:
                logger.error(f"Failed to load initial data: {e}")

        step_count = 0
        root_directive = TaskDirective(
            description="Process", priority=TaskPriority.SYSTEM
        )

        while step_count < self.max_steps:
            next_agent_name = self.determine_next_agent()
            if not next_agent_name:
                logger.info("No proposals. Workflow complete.")
                self.state = SystemState.COMPLETED
                break

            self.context.log_step(f"Running {next_agent_name}")

            # Use robust execute_proposal method
            result = self.execute_proposal(next_agent_name, root_directive)
            self.context = result.context
            self._last_status = result.status

            if result.status == AgentStatus.ERROR:
                self.state = SystemState.ERROR
                break

            if self.goal_manager.all_goals_achieved(self.context):
                logger.info("All goals achieved.")
                self.state = SystemState.COMPLETED
                break

            system_log.workflow_phase("execute", step_count)
            step_count += 1

        system_log.info("=== Workflow completed ===", extra={
            "type": "workflow_end",
            "state": self.state.value,
            "steps": step_count
        })

        if step_count >= self.max_steps:
            logger.warning("Max steps reached. Stopping.")
            self.state = SystemState.ERROR

        return self.context
