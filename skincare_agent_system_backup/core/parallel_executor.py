"""
Parallel Executor: Concurrent agent execution with dependency management.
Replaces sequential execution with true parallel processing.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Set

if TYPE_CHECKING:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.models import AgentContext, AgentResult

logger = logging.getLogger("ParallelExecutor")


@dataclass
class AgentDependency:
    """Defines execution dependencies for an agent."""

    agent_name: str
    depends_on: List[str] = field(default_factory=list)  # Must complete first
    can_parallel_with: List[str] = field(default_factory=list)  # Can run together
    blocks: List[str] = field(default_factory=list)  # Cannot run with these


@dataclass
class ExecutionTier:
    """A tier of agents that can run in parallel."""

    tier_number: int
    agents: List[str]
    dependencies_met: bool = True


@dataclass
class ParallelExecutionResult:
    """Result of parallel execution."""

    tier_number: int
    results: Dict[str, "AgentResult"]
    duration_ms: float
    errors: Dict[str, str]
    cancelled: List[str]


class DependencyGraph:
    """
    Manages agent execution order based on dependencies.

    Supports:
    - Sequential dependencies (A must complete before B)
    - Parallel execution (A and B can run together)
    - Blocking relations (A cannot run with B)
    """

    def __init__(self):
        self._dependencies: Dict[str, AgentDependency] = {}
        self._reverse_deps: Dict[str, Set[str]] = {}  # Who depends on me

    def add_dependency(self, dep: AgentDependency) -> None:
        """Add agent dependency information."""
        self._dependencies[dep.agent_name] = dep

        # Build reverse dependency map
        for d in dep.depends_on:
            if d not in self._reverse_deps:
                self._reverse_deps[d] = set()
            self._reverse_deps[d].add(dep.agent_name)

        logger.debug(f"Added dependency: {dep.agent_name} depends on {dep.depends_on}")

    def remove_dependency(self, agent_name: str) -> None:
        """Remove an agent from the dependency graph."""
        if agent_name in self._dependencies:
            del self._dependencies[agent_name]

        # Clean up reverse deps
        for deps in self._reverse_deps.values():
            deps.discard(agent_name)

    def get_dependencies(self, agent_name: str) -> List[str]:
        """Get agents that must complete before this agent."""
        dep = self._dependencies.get(agent_name)
        return dep.depends_on if dep else []

    def get_dependents(self, agent_name: str) -> Set[str]:
        """Get agents that depend on this agent."""
        return self._reverse_deps.get(agent_name, set())

    def can_run_parallel(self, agent_a: str, agent_b: str) -> bool:
        """Check if two agents can run in parallel."""
        dep_a = self._dependencies.get(agent_a)
        dep_b = self._dependencies.get(agent_b)

        # Check if either blocks the other
        if dep_a and agent_b in dep_a.blocks:
            return False
        if dep_b and agent_a in dep_b.blocks:
            return False

        # Check if either depends on the other
        if dep_a and agent_b in dep_a.depends_on:
            return False
        if dep_b and agent_a in dep_b.depends_on:
            return False

        # Explicitly allowed parallel or no restrictions
        if dep_a and agent_b in dep_a.can_parallel_with:
            return True
        if dep_b and agent_a in dep_b.can_parallel_with:
            return True

        # Default: allow parallel if no blocking dependencies
        return True

    def get_ready_agents(self, completed: Set[str]) -> List[str]:
        """Get agents whose dependencies are satisfied."""
        ready = []

        for name, dep in self._dependencies.items():
            if name in completed:
                continue

            # Check if all dependencies are met
            deps_met = all(d in completed for d in dep.depends_on)
            if deps_met:
                ready.append(name)

        return ready

    def topological_sort(self) -> List[List[str]]:
        """
        Sort agents into execution tiers.

        Returns:
            List of tiers, where each tier contains agents
            that can run in parallel.
        """
        tiers: List[List[str]] = []
        completed: Set[str] = set()
        all_agents = set(self._dependencies.keys())

        while completed != all_agents:
            # Get agents ready to run
            ready = self.get_ready_agents(completed)

            if not ready:
                # Circular dependency or all done
                remaining = all_agents - completed
                if remaining:
                    logger.warning(f"Possible circular dependency: {remaining}")
                    # Add remaining as final tier anyway
                    tiers.append(list(remaining))
                break

            # Group ready agents by parallel compatibility
            tier = self._group_parallel_agents(ready)
            tiers.append(tier)
            completed.update(tier)

        return tiers

    def _group_parallel_agents(self, agents: List[str]) -> List[str]:
        """Group agents that can run in parallel."""
        if len(agents) <= 1:
            return agents

        # For simplicity, return all ready agents as one tier
        # A more sophisticated implementation would check
        # can_run_parallel for each pair
        compatible = [agents[0]]

        for agent in agents[1:]:
            can_add = all(
                self.can_run_parallel(agent, existing) for existing in compatible
            )
            if can_add:
                compatible.append(agent)

        return compatible

    def visualize(self) -> str:
        """Generate ASCII visualization of dependency graph."""
        lines = ["Dependency Graph:"]
        lines.append("-" * 40)

        for name, dep in self._dependencies.items():
            deps = ", ".join(dep.depends_on) if dep.depends_on else "none"
            parallel = (
                ", ".join(dep.can_parallel_with) if dep.can_parallel_with else "any"
            )
            lines.append(f"{name}:")
            lines.append(f"  depends on: {deps}")
            lines.append(f"  parallel with: {parallel}")

        lines.append("-" * 40)
        tiers = self.topological_sort()
        lines.append("Execution Tiers:")
        for i, tier in enumerate(tiers):
            lines.append(f"  Tier {i + 1}: {', '.join(tier)}")

        return "\n".join(lines)


class ParallelExecutor:
    """
    Executes multiple agents concurrently with dependency management.

    Features:
    - Parallel execution of independent agents
    - Dependency-based ordering
    - Timeout handling
    - Result aggregation
    - Graceful error handling
    """

    def __init__(self, timeout: float = 60.0, max_concurrent: int = 5):
        self._timeout = timeout
        self._max_concurrent = max_concurrent
        self._dependency_graph = DependencyGraph()
        self._results: Dict[str, "AgentResult"] = {}
        self._execution_history: List[ParallelExecutionResult] = []

    @property
    def dependency_graph(self) -> DependencyGraph:
        return self._dependency_graph

    def configure_dependencies(self, dependencies: List[AgentDependency]) -> None:
        """Configure agent dependencies."""
        for dep in dependencies:
            self._dependency_graph.add_dependency(dep)

    async def run_parallel(
        self,
        agents: Dict[str, "BaseAgent"],
        context: "AgentContext",
        directive: Any = None,
    ) -> Dict[str, "AgentResult"]:
        """
        Execute agents concurrently respecting dependencies.

        Args:
            agents: Dict of agent_name -> agent instance
            context: Shared agent context
            directive: Optional task directive

        Returns:
            Dict mapping agent_name to result
        """
        logger.info(f"Starting parallel execution of {len(agents)} agents")

        # Ensure all agents are in dependency graph
        for name in agents.keys():
            if name not in self._dependency_graph._dependencies:
                self._dependency_graph.add_dependency(
                    AgentDependency(
                        agent_name=name,
                        depends_on=[],
                        can_parallel_with=list(agents.keys()),
                    )
                )

        # Get execution tiers
        tiers = self._dependency_graph.topological_sort()
        logger.info(f"Execution plan: {len(tiers)} tiers")

        self._results = {}
        completed: Set[str] = set()

        for tier_num, tier_agents in enumerate(tiers, 1):
            # Filter to agents we actually have
            tier_agents = [a for a in tier_agents if a in agents]

            if not tier_agents:
                continue

            logger.info(f"Executing tier {tier_num}: {tier_agents}")

            # Execute tier
            tier_result = await self._execute_tier(
                tier_number=tier_num,
                agent_names=tier_agents,
                agents=agents,
                context=context,
                directive=directive,
            )

            # Store results
            self._results.update(tier_result.results)
            self._execution_history.append(tier_result)

            # Update completed set
            completed.update(tier_agents)

            # Check for critical errors
            if tier_result.errors:
                logger.warning(f"Tier {tier_num} had errors: {tier_result.errors}")
                # Continue anyway - partial completion is better than stopping

        logger.info(f"Parallel execution complete: {len(self._results)} results")
        return self._results

    async def _execute_tier(
        self,
        tier_number: int,
        agent_names: List[str],
        agents: Dict[str, "BaseAgent"],
        context: "AgentContext",
        directive: Any,
    ) -> ParallelExecutionResult:
        """Execute a tier of agents in parallel."""
        start_time = datetime.now()
        results: Dict[str, "AgentResult"] = {}
        errors: Dict[str, str] = {}
        cancelled: List[str] = []

        # Create tasks for each agent
        tasks: Dict[str, asyncio.Task] = {}

        for name in agent_names[: self._max_concurrent]:
            agent = agents.get(name)
            if not agent:
                continue

            task = asyncio.create_task(
                self._execute_agent_async(agent, context, directive),
                name=f"agent_{name}",
            )
            tasks[name] = task

        if not tasks:
            return ParallelExecutionResult(
                tier_number=tier_number,
                results={},
                duration_ms=0,
                errors={},
                cancelled=[],
            )

        # Wait for all with timeout
        try:
            done, pending = await asyncio.wait(
                tasks.values(), timeout=self._timeout, return_when=asyncio.ALL_COMPLETED
            )

            # Collect results
            for name, task in tasks.items():
                if task in done:
                    try:
                        result = task.result()
                        results[name] = result
                    except Exception as e:
                        errors[name] = str(e)
                        logger.error(f"Agent {name} failed: {e}")
                else:
                    # Task didn't complete in time
                    cancelled.append(name)
                    task.cancel()
                    logger.warning(f"Agent {name} cancelled (timeout)")

        except Exception as e:
            logger.error(f"Tier execution error: {e}")
            errors["_tier"] = str(e)

        duration = (datetime.now() - start_time).total_seconds() * 1000

        return ParallelExecutionResult(
            tier_number=tier_number,
            results=results,
            duration_ms=duration,
            errors=errors,
            cancelled=cancelled,
        )

    async def _execute_agent_async(
        self, agent: "BaseAgent", context: "AgentContext", directive: Any
    ) -> "AgentResult":
        """Execute a single agent asynchronously."""
        loop = asyncio.get_event_loop()

        # Check if agent has async run method
        if hasattr(agent, "run_async"):
            return await agent.run_async(context, directive)
        else:
            # Run sync method in executor
            return await loop.run_in_executor(None, agent.run, context, directive)

    def aggregate_results(
        self, results: Dict[str, "AgentResult"], context: "AgentContext"
    ) -> "AgentContext":
        """
        Aggregate results from multiple agents into context.

        Args:
            results: Dict of agent results
            context: Context to update

        Returns:
            Updated context
        """
        for agent_name, result in results.items():
            # Context is already updated by agent.run()
            # This merges any additional data

            # Log decisions
            context.log_decision(
                "ParallelExecutor",
                f"Agent {agent_name} completed: {result.status.value}",
            )

        return context

    def get_execution_history(self) -> List[ParallelExecutionResult]:
        """Get history of parallel executions."""
        return self._execution_history.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total_executions = len(self._execution_history)
        total_agents = sum(len(r.results) for r in self._execution_history)
        total_errors = sum(len(r.errors) for r in self._execution_history)
        total_cancelled = sum(len(r.cancelled) for r in self._execution_history)

        avg_duration = 0
        if total_executions > 0:
            avg_duration = (
                sum(r.duration_ms for r in self._execution_history) / total_executions
            )

        return {
            "total_executions": total_executions,
            "total_agents_executed": total_agents,
            "total_errors": total_errors,
            "total_cancelled": total_cancelled,
            "average_tier_duration_ms": avg_duration,
            "timeout_seconds": self._timeout,
            "max_concurrent": self._max_concurrent,
        }


# Default dependency configurations
def get_default_dependencies() -> List[AgentDependency]:
    """Get default agent dependencies for content generation workflow."""
    return [
        AgentDependency(
            agent_name="DataAgent", depends_on=[], can_parallel_with=[], blocks=[]
        ),
        AgentDependency(
            agent_name="SyntheticDataAgent",
            depends_on=["DataAgent"],
            can_parallel_with=[],
            blocks=[],
        ),
        AgentDependency(
            agent_name="DelegatorAgent",
            depends_on=["DataAgent", "SyntheticDataAgent"],
            can_parallel_with=[],
            blocks=[],
        ),
        AgentDependency(
            agent_name="GenerationAgent",
            depends_on=["DelegatorAgent"],
            can_parallel_with=[],
            blocks=[],
        ),
        AgentDependency(
            agent_name="VerifierAgent",
            depends_on=["GenerationAgent"],
            can_parallel_with=[],
            blocks=[],
        ),
    ]


def create_parallel_executor(
    timeout: float = 60.0, use_default_deps: bool = True
) -> ParallelExecutor:
    """Create a configured parallel executor."""
    executor = ParallelExecutor(timeout=timeout)

    if use_default_deps:
        executor.configure_dependencies(get_default_dependencies())

    return executor
