# skincare_agent_system/cognition/llm_reasoning.py
"""LLM-powered reasoning for agent decisions"""

from typing import Dict, Any, Optional
import json
from ..infrastructure.llm_client import llm_client

class ReasoningEngine:
    """Provides LLM-based reasoning capabilities to agents"""
    
    def __init__(self, llm_provider=None):
        self.llm = llm_provider or llm_client
    
    def reason_about_action(
        self,
        agent_name: str,
        task_description: str,
        context_summary: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Have LLM reason about whether agent should act.
        
        Returns:
            {
                "should_act": bool,
                "confidence": float,
                "reasoning": str,
                "complexity": str,
                "risks": List[str],
                "alternatives": List[str]
            }
        """
        prompt = self._build_reasoning_prompt(
            agent_name, task_description, context_summary, constraints
        )
        
        try:
            response = self.llm.generate(prompt, temperature=0.3)
            return self._parse_reasoning_response(response)
        except Exception as e:
            return self._fallback_reasoning(context_summary)
    
    def _build_reasoning_prompt(
        self, 
        agent_name: str, 
        task: str, 
        context: Dict, 
        constraints: Optional[Dict]
    ) -> str:
        return f"""
You are {agent_name}, an AI agent in a multi-agent system.

Your task: {task}

Current context:
{json.dumps(context, indent=2)}

Constraints:
{json.dumps(constraints or {}, indent=2)}

Perform chain-of-thought reasoning:

1. **Prerequisites Check**: Do I have everything needed to complete this task?
2. **Capability Assessment**: Am I the right agent for this task?
3. **Complexity Analysis**: How difficult is this task given the current context?
4. **Risk Assessment**: What could go wrong?
5. **Confidence Calculation**: How confident am I (0.0-1.0) in completing this successfully?
6. **Action Decision**: Should I act now, or should another agent handle this?

Respond ONLY with valid JSON:
{{
    "should_act": true,
    "confidence": 0.85,
    "reasoning": "detailed chain of thought explaining your decision",
    "complexity": "medium",
    "prerequisites_met": true,
    "risks": ["potential issue 1", "potential issue 2"],
    "alternatives": ["alternative approach 1"]
}}
"""
    
    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """Parse and validate LLM reasoning response"""
        # Remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        parsed = json.loads(cleaned)
        
        # Validate required fields
        required = ['should_act', 'confidence', 'reasoning']
        if not all(k in parsed for k in required):
            raise ValueError(f"Missing required fields: {required}")
        
        # Validate types and ranges
        if not isinstance(parsed['should_act'], bool):
            raise ValueError("should_act must be boolean")
        
        if not (0.0 <= parsed['confidence'] <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        
        return parsed
    
    def _fallback_reasoning(self, context: Dict) -> Dict[str, Any]:
        """Heuristic fallback when LLM unavailable"""
        has_required_data = all(
            context.get(k) is not None 
            for k in ['product_data', 'workflow_phase']
        )
        
        return {
            "should_act": has_required_data,
            "confidence": 0.7 if has_required_data else 0.0,
            "reasoning": "Heuristic decision based on data availability",
            "complexity": "medium",
            "prerequisites_met": has_required_data,
            "risks": ["LLM unavailable - using heuristics"],
            "alternatives": []
        }

# Global instance
reasoning_engine = ReasoningEngine()