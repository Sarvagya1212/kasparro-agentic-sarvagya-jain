"""
Cognition module: Advanced reasoning and reflection capabilities.
"""

from skincare_agent_system.cognition.reasoning import (
    ChainOfThought,
    ReActReasoner,
    ReasoningChain,
    ThoughtType,
)
from skincare_agent_system.cognition.reflection import (
    SelfReflector,
    ReflectionResult,
    ReflectionIssue,
)
from skincare_agent_system.cognition.react_reasoning import (
    ReActLoop,
    ReActStep,
    ReActResult,
    ConversationHistory,
    create_react_loop,
)
from skincare_agent_system.cognition.agent_goals import (
    AgentGoal,
    AgentGoalManager,
    GoalStatus,
    GoalProgress,
    create_default_goals,
)
from skincare_agent_system.cognition.expert_system import (
    ExpertSystem,
    DecisionTree,
    ConfidenceCalibrator,
    get_expert_system,
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
