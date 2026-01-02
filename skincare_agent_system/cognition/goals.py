# skincare_agent_system/cognition/goals.py

from dataclasses import dataclass
from typing import List, Dict, Any, Callable
from enum import Enum

class GoalStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    FAILED = "failed"
    BLOCKED = "blocked"

@dataclass
class Goal:
    """Represents an agent goal"""
    description: str
    success_criteria: Callable[[Dict], bool]  # Function to check if achieved
    priority: int = 5
    status: GoalStatus = GoalStatus.PENDING
    subgoals: List['Goal'] = None
    metadata: Dict[str, Any] = None
    
    def evaluate(self, context: Dict) -> bool:
        """Check if goal is achieved"""
        try:
            return self.success_criteria(context)
        except Exception as e:
            logger.error(f"Goal evaluation failed: {e}")
            return False

class GoalDrivenAgent(BaseAgent):
    """Base class for agents with explicit goals"""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.goals: List[Goal] = []
        self._init_goals()
    
    @abstractmethod
    def _init_goals(self):
        """Initialize agent's goals - override in subclasses"""
        pass
    
    def evaluate_goals(self, context: AgentContext) -> Dict[str, Any]:
        """
        Evaluate all goals and return status.
        
        Returns:
            {
                "achieved": List[Goal],
                "pending": List[Goal],
                "blocked": List[Goal],
                "progress": float  # 0.0-1.0
            }
        """
        context_dict = context.dict() if hasattr(context, 'dict') else context.__dict__
        
        achieved = []
        pending = []
        blocked = []
        
        for goal in self.goals:
            if goal.evaluate(context_dict):
                goal.status = GoalStatus.ACHIEVED
                achieved.append(goal)
            elif self._is_goal_blocked(goal, context_dict):
                goal.status = GoalStatus.BLOCKED
                blocked.append(goal)
            else:
                goal.status = GoalStatus.PENDING
                pending.append(goal)
        
        total_goals = len(self.goals)
        progress = len(achieved) / total_goals if total_goals > 0 else 0.0
        
        return {
            "achieved": achieved,
            "pending": pending,
            "blocked": blocked,
            "progress": progress
        }
    
    def _is_goal_blocked(self, goal: Goal, context: Dict) -> bool:
        """Check if goal is blocked by missing prerequisites"""
        # Override in subclasses for custom logic
        return False
    
    def propose(self, context: AgentContext) -> AgentProposal:
        """Generate proposal driven by goal progress"""
        # Evaluate current goal status
        goal_status = self.evaluate_goals(context)
        
        # Get LLM reasoning
        assessment = self.assess_context(context)
        
        # Adjust confidence based on goal progress
        base_confidence = assessment['confidence']
        
        # Boost confidence if we're making progress toward goals
        if goal_status['progress'] > 0.5:
            base_confidence = min(1.0, base_confidence * 1.1)
        
        # Lower confidence if goals are blocked
        if goal_status['blocked']:
            base_confidence *= 0.7
        
        # Add goal context to reasoning
        goal_context = f"""
Goal Progress: {goal_status['progress']:.0%}
- Achieved: {len(goal_status['achieved'])} goals
- Pending: {len(goal_status['pending'])} goals
- Blocked: {len(goal_status['blocked'])} goals

Original reasoning: {assessment['reasoning']}
"""
        
        return AgentProposal(
            agent_name=self.name,
            action=self._determine_action(context, assessment),
            confidence=base_confidence,
            reason=goal_context,
            preconditions_met=assessment['prerequisites_met'],
            priority=self._calculate_priority_with_goals(context, assessment, goal_status)
        )
    
    def _calculate_priority_with_goals(
        self, 
        context: AgentContext, 
        assessment: Dict,
        goal_status: Dict
    ) -> int:
        """Calculate priority considering goal progress"""
        base_priority = super()._calculate_priority(context, assessment)
        
        # Higher priority if we have pending goals
        if goal_status['pending']:
            base_priority += len(goal_status['pending'])
        
        # Lower priority if goals are blocked
        if goal_status['blocked']:
            base_priority -= 2
        
        return max(0, min(10, base_priority))