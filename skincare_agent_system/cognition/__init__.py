"""
Cognition module: Advanced reasoning and reflection capabilities.
"""

from skincare_agent_system.cognition.agent_goals import (
    AgentGoal,
    AgentGoalManager,
    GoalProgress,
    GoalStatus,
    create_default_goals,
)
from skincare_agent_system.cognition.expert_system import (
    ConfidenceCalibrator,
    DecisionTree,
    ExpertSystem,
    get_expert_system,
)
from skincare_agent_system.cognition.react_reasoning import (
    ConversationHistory,
    ReActLoop,
    ReActResult,
    ReActStep,
    create_react_loop,
)
from skincare_agent_system.cognition.reasoning import (
    ChainOfThought,
    ReActReasoner,
    ReasoningChain,
    ThoughtType,
)
from skincare_agent_system.cognition.reflection import (
    ReflectionIssue,
    ReflectionResult,
    SelfReflector,
)

__all__ = [
    # Reasoning
    "ChainOfThought",
    "ReActReasoner",
    "ReasoningChain",
    "ThoughtType",
    # Reflection
    "SelfReflector",
    "ReflectionResult",
    "ReflectionIssue",
    # ReAct Loop
    "ReActLoop",
    "ReActStep",
    "ReActResult",
    "ConversationHistory",
    "create_react_loop",
    # Agent Goals
    "AgentGoal",
    "AgentGoalManager",
    "GoalStatus",
    "GoalProgress",
    "create_default_goals",
    # Expert System
    "ExpertSystem",
    "DecisionTree",
    "ConfidenceCalibrator",
    "get_expert_system",
]
