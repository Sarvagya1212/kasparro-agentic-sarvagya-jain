"""
Simplified Base Agent.
Stripped of advanced cognition for Phase 1 Simplified Version.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
)

logger = logging.getLogger("BaseAgent")


from ..cognition.llm_reasoning import reasoning_engine

class BaseAgent(ABC):
    """Enhanced base agent with LLM reasoning"""
    
    def __init__(self, name: str, llm_provider=None):
        self.name = name
        self.llm = llm_provider
        self.reasoning = reasoning_engine
    
    @abstractmethod
    def get_task_description(self) -> str:
        """Return a clear description of what this agent does"""
        pass
    
    def assess_context(self, context: AgentContext) -> Dict[str, Any]:
        """
        Use LLM reasoning to assess whether to act.
        
        Override this in subclasses for custom reasoning, or rely on default.
        """
        context_summary = {
            "product_data_available": context.product_data is not None,
            "workflow_phase": context.workflow_phase,
            "analysis_complete": bool(context.analysis_results),
            "validation_status": context.is_valid
        }
        
        return self.reasoning.reason_about_action(
            agent_name=self.name,
            task_description=self.get_task_description(),
            context_summary=context_summary
        )
    
    def propose(self, context: AgentContext, directive: str) -> AgentProposal:
        """Generate proposal using LLM reasoning"""
        assessment = self.assess_context(context)
        
        return AgentProposal(
            agent_name=self.name,
            action=self._determine_action(context, assessment),
            confidence=assessment['confidence'],
            reason=assessment['reasoning'],  # ✅ Real reasoning
            preconditions_met=assessment['prerequisites_met'],
            priority=self._calculate_priority(context, assessment)
        )
    
    @abstractmethod
    def _determine_action(self, context: AgentContext, assessment: Dict) -> str:
        """Determine specific action based on assessment"""
        pass
    
    def _calculate_priority(self, context: AgentContext, assessment: Dict) -> int:
        """Calculate priority based on assessment"""
        base = 5
        
        # Higher confidence = higher priority
        if assessment['confidence'] > 0.8:
            base += 2
        elif assessment['confidence'] < 0.5:
            base -= 2
        
        # Complexity affects priority
        complexity_map = {"low": 1, "medium": 0, "high": -1}
        base += complexity_map.get(assessment.get('complexity', 'medium'), 0)
        
        return max(0, min(10, base))