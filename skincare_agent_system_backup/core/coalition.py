"""
Coalition Execution: Parallel execution of agent coalitions.
Replaces fake coalition formation with real distributed task execution.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.models import AgentContext


logger = logging.getLogger("Coalition")


class CoalitionStatus(Enum):
    """Status of a coalition."""

    FORMING = "forming"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some members completed


@dataclass
class CoalitionMember:
    """A member of a coalition."""

    agent_name: str
    role: str  # lead, support, validator
    task: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class CoalitionTask:
    """Task to be distributed among coalition members."""

    task_id: str
    description: str
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(
        default_factory=dict
    )  # subtask -> depends_on
    parallel_groups: List[List[str]] = field(
        default_factory=list
    )  # Groups that can run together


@dataclass
class CoalitionResult:
    """Result of coalition execution."""

    coalition_id: str
    status: CoalitionStatus
    member_results: Dict[str, Any]
    aggregated_result: Optional[Any] = None
    duration_ms: float = 0.0
    error: Optional[str] = None


class Coalition:
    """
    A coalition of agents working together on a task.

    Features:
    - Task distribution among members
    - Parallel execution
    - Result aggregation
    - Failure handling
    """

    def __init__(self, coalition_id: str, lead_agent: str, task: CoalitionTask):
        self.coalition_id = coalition_id
        self.lead_agent = lead_agent
        self.task = task
        self.members: Dict[str, CoalitionMember] = {}
        self.status = CoalitionStatus.FORMING
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self._result: Optional[CoalitionResult] = None

    def add_member(
        self, agent_name: str, role: str, assigned_task: str
    ) -> CoalitionMember:
        """Add a member to the coalition."""
        member = CoalitionMember(agent_name=agent_name, role=role, task=assigned_task)
        self.members[agent_name] = member
        logger.info(f"Added {agent_name} to coalition {self.coalition_id} as {role}")
        return member

    def remove_member(self, agent_name: str) -> bool:
        """Remove a member from the coalition."""
        if agent_name in self.members:
            del self.members[agent_name]
            return True
        return False

    def is_ready(self) -> bool:
        """Check if coalition is ready to execute."""
        return len(self.members) > 0 and self.status == CoalitionStatus.FORMING

    def mark_ready(self) -> None:
        """Mark coalition as ready for execution."""
        self.status = CoalitionStatus.READY

    async def execute(
        self,
        agents: Dict[str, "BaseAgent"],
        context: "AgentContext",
        timeout: float = 60.0,
    ) -> CoalitionResult:
        """
        Execute coalition tasks in parallel.
        """
        if not self.is_ready() and self.status != CoalitionStatus.READY:
            self.mark_ready()

        self.status = CoalitionStatus.EXECUTING
        start_time = datetime.now()
        member_results: Dict[str, Any] = {}

        logger.info(
            f"Coalition {self.coalition_id} executing with {len(self.members)} members"
        )

        try:
            # Group tasks by dependencies
            execution_groups = self._compute_execution_order()

            for group in execution_groups:
                # Execute group in parallel
                tasks = []
                for agent_name in group:
                    member = self.members.get(agent_name)
                    agent = agents.get(agent_name)

                    if not member or not agent:
                        continue

                    member.status = "running"
                    member.started_at = datetime.now().isoformat()

                    task = asyncio.create_task(
                        self._execute_member(agent, member, context),
                        name=f"coalition_{agent_name}",
                    )
                    tasks.append((agent_name, task))

                # Wait for group with timeout
                if tasks:
                    done, pending = await asyncio.wait(
                        [t for _, t in tasks],
                        timeout=timeout / len(execution_groups),
                        return_when=asyncio.ALL_COMPLETED,
                    )

                    # Collect results
                    for agent_name, task in tasks:
                        member = self.members[agent_name]

                        if task in done:
                            try:
                                result = task.result()
                                member.result = result
                                member.status = "completed"
                                member_results[agent_name] = result
                            except Exception as e:
                                member.status = "failed"
                                member.error = str(e)
                        else:
                            task.cancel()
                            member.status = "failed"
                            member.error = "Timeout"

                        member.completed_at = datetime.now().isoformat()

            # Determine final status
            completed = sum(1 for m in self.members.values() if m.status == "completed")
            failed = sum(1 for m in self.members.values() if m.status == "failed")

            if failed == 0:
                self.status = CoalitionStatus.COMPLETED
            elif completed > 0:
                self.status = CoalitionStatus.PARTIAL
            else:
                self.status = CoalitionStatus.FAILED

            # Aggregate results
            aggregated = self._aggregate_results(member_results)

        except Exception as e:
            self.status = CoalitionStatus.FAILED
            logger.error(f"Coalition execution failed: {e}")

            self._result = CoalitionResult(
                coalition_id=self.coalition_id,
                status=self.status,
                member_results={},
                error=str(e),
                duration_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )
            return self._result

        self.completed_at = datetime.now().isoformat()
        duration = (datetime.now() - start_time).total_seconds() * 1000

        self._result = CoalitionResult(
            coalition_id=self.coalition_id,
            status=self.status,
            member_results=member_results,
            aggregated_result=aggregated,
            duration_ms=duration,
        )

        logger.info(
            f"Coalition {self.coalition_id} {self.status.value}: "
            f"{completed}/{len(self.members)} completed"
        )

        return self._result

    async def _execute_member(
        self, agent: "BaseAgent", member: CoalitionMember, context: "AgentContext"
    ) -> Any:
        """Execute a single coalition member's task."""
        try:
            # Create task directive for the member
            from skincare_agent_system.core.models import TaskDirective, TaskPriority

            directive = TaskDirective(
                description=member.task,
                priority=TaskPriority.SYSTEM,
                parameters={"coalition_id": self.coalition_id, "role": member.role},
            )

            # Execute agent
            if hasattr(agent, "run_async"):
                result = await agent.run_async(context, directive)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, agent.run, context, directive)

            return result

        except Exception as e:
            logger.error(f"Member {member.agent_name} failed: {e}")
            raise

    def _compute_execution_order(self) -> List[List[str]]:
        """
        Compute parallel execution groups respecting dependencies.
        """
        if self.task.parallel_groups:
            return self.task.parallel_groups

        # If no explicit groups, use dependencies to compute
        if not self.task.dependencies:
            # All can run in parallel
            return [list(self.members.keys())]

        # Topological sort based on dependencies
        groups: List[List[str]] = []
        remaining = set(self.members.keys())
        completed: Set[str] = set()

        while remaining:
            # Find agents with satisfied dependencies
            ready = []
            for agent in remaining:
                deps = self.task.dependencies.get(agent, [])
                if all(d in completed for d in deps):
                    ready.append(agent)

            if not ready:
                # Circular dependency or all remaining have unsatisfied deps
                ready = list(remaining)

            groups.append(ready)
            completed.update(ready)
            remaining -= set(ready)

        return groups

    def _aggregate_results(
        self, member_results: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate results from all members.
        """
        if not member_results:
            return None

        aggregated = {
            "total_members": len(self.members),
            "completed": sum(
                1 for m in self.members.values() if m.status == "completed"
            ),
            "results": {},
            "combined_data": {},
        }

        for agent_name, result in member_results.items():
            member = self.members[agent_name]
            aggregated["results"][agent_name] = {
                "role": member.role,
                "task": member.task,
                "success": member.status == "completed",
            }

            # Combine context data from results
            if hasattr(result, "context") and result.context:
                ctx = result.context
                if hasattr(ctx, "analysis_results") and ctx.analysis_results:
                    if "analysis" not in aggregated["combined_data"]:
                        aggregated["combined_data"]["analysis"] = {}
                    aggregated["combined_data"]["analysis"][agent_name] = True

        return aggregated

    @property
    def result(self) -> Optional[CoalitionResult]:
        return self._result


class CoalitionManager:
    """
    Manages coalition lifecycle.
    """

    def __init__(self):
        self._coalitions: Dict[str, Coalition] = {}
        self._history: List[CoalitionResult] = []

    def create_coalition(
        self,
        lead_agent: str,
        task_description: str,
        subtasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Coalition:
        """Create a new coalition."""
        coalition_id = f"coal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        task = CoalitionTask(
            task_id=f"task_{coalition_id}",
            description=task_description,
            subtasks=subtasks or [],
        )

        coalition = Coalition(
            coalition_id=coalition_id, lead_agent=lead_agent, task=task
        )

        # Add lead agent
        coalition.add_member(lead_agent, "lead", "coordinate and aggregate")

        self._coalitions[coalition_id] = coalition
        logger.info(f"Created coalition {coalition_id} led by {lead_agent}")

        return coalition

    def get_coalition(self, coalition_id: str) -> Optional[Coalition]:
        """Get a coalition by ID."""
        return self._coalitions.get(coalition_id)

    def disband_coalition(self, coalition_id: str) -> bool:
        """Disband a coalition."""
        if coalition_id in self._coalitions:
            coalition = self._coalitions.pop(coalition_id)
            if coalition.result:
                self._history.append(coalition.result)
            return True
        return False

    async def execute_coalition(
        self, coalition_id: str, agents: Dict[str, "BaseAgent"], context: "AgentContext"
    ) -> Optional[CoalitionResult]:
        """Execute a coalition."""
        coalition = self._coalitions.get(coalition_id)
        if not coalition:
            return None

        result = await coalition.execute(agents, context)
        self._history.append(result)

        return result

    def get_active_coalitions(self) -> List[Coalition]:
        """Get all active coalitions."""
        return [
            c
            for c in self._coalitions.values()
            if c.status
            in [
                CoalitionStatus.FORMING,
                CoalitionStatus.READY,
                CoalitionStatus.EXECUTING,
            ]
        ]

    def get_history(self, limit: int = 20) -> List[CoalitionResult]:
        """Get coalition execution history."""
        return self._history[-limit:]


# Singleton
_coalition_manager: Optional[CoalitionManager] = None


def get_coalition_manager() -> CoalitionManager:
    """Get or create coalition manager singleton."""
    global _coalition_manager
    if _coalition_manager is None:
        _coalition_manager = CoalitionManager()
    return _coalition_manager


def reset_coalition_manager() -> None:
    """Reset coalition manager (for testing)."""
    global _coalition_manager
    _coalition_manager = None
