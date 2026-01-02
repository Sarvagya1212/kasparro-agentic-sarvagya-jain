"""
Core module: Orchestration, proposals, state management, and execution.

Note: Some imports are lazy to avoid circular dependencies.
"""

from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
    SystemState,
)
from skincare_agent_system.core.proposals import (
    AgentProposal,
    ProposalSystem,
    Event,
    EventType,
    EventBus,
    AsyncEventBus,
    Goal,
    GoalManager,
)
from skincare_agent_system.core.state_manager import StateManager
from skincare_agent_system.core.context_analyzer import (
    ContextAnalyzer,
    get_context_analyzer,
)

# Phase 1-2 Autonomy Upgrades (lazy imports to avoid circular deps)
from skincare_agent_system.core.agent_activation import (
    AgentState,
    ActivationTrigger,
    ActivationRequest,
)
from skincare_agent_system.core.parallel_executor import (
    DependencyGraph,
    AgentDependency,
    ExecutionTier,
    ParallelExecutionResult,
    get_default_dependencies,
)
from skincare_agent_system.core.event_supervisor import (
    EventRule,
    SupervisorState,
)
from skincare_agent_system.core.preemption import (
    AgentCheckpoint,
    CancellationRequest,
    CancellationState,
    PreemptionEvent,
)

# These require BaseAgent and are imported lazily
def get_orchestrator():
    """Lazily import Orchestrator to avoid circular deps."""
    from skincare_agent_system.core.orchestrator import Orchestrator
    return Orchestrator

def get_agent_activator():
    """Lazily import AgentActivator to avoid circular deps."""
    from skincare_agent_system.core.agent_activation import get_agent_activator as _get
    return _get()

def get_parallel_executor():
    """Lazily import ParallelExecutor to avoid circular deps."""
    from skincare_agent_system.core.parallel_executor import create_parallel_executor
    return create_parallel_executor()

def get_event_supervisor():
    """Lazily import EventSupervisor to avoid circular deps."""
    from skincare_agent_system.core.event_supervisor import create_event_supervisor
    return create_event_supervisor()

def get_preemption_manager():
    """Lazily import PreemptionManager to avoid circular deps."""
    from skincare_agent_system.core.preemption import get_preemption_manager as _get
    return _get()


__all__ = [
    # Models
    "AgentContext",
    "AgentResult",
    "AgentStatus",
    "TaskDirective",
    "TaskPriority",
    "SystemState",
    # Proposals
    "AgentProposal",
    "ProposalSystem",
    "Event",
    "EventType",
    "EventBus",
    "AsyncEventBus",
    "Goal",
    "GoalManager",
    # State
    "StateManager",
    # Context
    "ContextAnalyzer",
    "get_context_analyzer",
    # Lazy loaders
    "get_orchestrator",
    "get_agent_activator",
    "get_parallel_executor",
    "get_event_supervisor",
    "get_preemption_manager",
    # Activation
    "AgentState",
    "ActivationTrigger",
    "ActivationRequest",
    # Parallel Execution
    "DependencyGraph",
    "AgentDependency",
    "ExecutionTier",
    "ParallelExecutionResult",
    "get_default_dependencies",
    # Event Supervisor
    "EventRule",
    "SupervisorState",
    # Preemption
    "AgentCheckpoint",
    "CancellationRequest",
    "CancellationState",
    "PreemptionEvent",
]
