"""
ReAct Reasoning: Thought → Action → Observation → Thought loop.
Implements true LLM-driven agent reasoning for autonomous decision-making.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.core.models import AgentContext
    from skincare_agent_system.core.proposals import AgentProposal

logger = logging.getLogger("ReAct")


@dataclass
class ReActStep:
    """A single step in the ReAct reasoning loop."""

    step_number: int
    thought: str  # Reasoning about current state
    action: Optional[str] = None  # Chosen action (if any)
    action_input: Optional[Dict[str, Any]] = None  # Input to the action
    observation: Optional[str] = None  # Result of action
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_prompt_format(self) -> str:
        """Format step for inclusion in LLM prompt."""
        parts = [f"Thought {self.step_number}: {self.thought}"]
        if self.action:
            parts.append(f"Action {self.step_number}: {self.action}")
            if self.action_input:
                parts.append(f"Action Input: {self.action_input}")
        if self.observation:
            parts.append(f"Observation {self.step_number}: {self.observation}")
        return "\n".join(parts)


@dataclass
class ReActResult:
    """Result of a ReAct reasoning loop."""

    final_thought: str
    final_action: str
    confidence: float
    reasoning_trace: List[ReActStep]
    success: bool
    error: Optional[str] = None


class ConversationHistory:
    """Maintains conversation context for multi-turn reasoning."""

    def __init__(self, max_turns: int = 20):
        self._history: List[Dict[str, str]] = []
        self._max_turns = max_turns

    def add_message(self, role: str, content: str) -> None:
        """Add a message to history."""
        self._history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # Trim if too long
        if len(self._history) > self._max_turns * 2:
            self._history = self._history[-self._max_turns:]

    def get_context_window(self, last_n: int = 10) -> List[Dict[str, str]]:
        """Get last n messages for context."""
        return self._history[-last_n:]

    def format_for_prompt(self, last_n: int = 5) -> str:
        """Format recent history for inclusion in prompt."""
        messages = self.get_context_window(last_n)
        if not messages:
            return "No previous conversation."

        formatted = []
        for msg in messages:
            role = msg["role"].upper()
            formatted.append(f"[{role}]: {msg['content']}")
        return "\n".join(formatted)

    def clear(self) -> None:
        """Clear conversation history."""
        self._history = []

    def __len__(self) -> int:
        return len(self._history)


class ReActLoop:
    """
    Implements the ReAct (Reasoning + Acting) pattern.

    The loop:
    1. THOUGHT: LLM reasons about current state and goal
    2. ACTION: LLM selects an action based on reasoning
    3. OBSERVATION: Action is executed, result observed
    4. Repeat until goal achieved or max iterations
    """

    # ReAct prompt template
    REACT_PROMPT_TEMPLATE = """You are an autonomous agent using ReAct (Reasoning + Acting) to achieve goals.

GOAL: {goal}

AVAILABLE ACTIONS:
{available_actions}

CURRENT CONTEXT:
{context_summary}

PREVIOUS REASONING:
{previous_steps}

CONVERSATION HISTORY:
{conversation_history}

Instructions:
1. First, write your THOUGHT about the current situation and what you need to do
2. Then, choose an ACTION from the available actions
3. Provide any ACTION INPUT if needed
4. Wait for the OBSERVATION

Format your response EXACTLY as:
Thought: [your reasoning about the current situation]
Action: [one of the available actions, or "FINISH" if goal is complete]
Action Input: [any parameters for the action, or "none"]

Begin:"""

    def __init__(
        self,
        llm_client: Any,
        max_iterations: int = 5,
        confidence_threshold: float = 0.7
    ):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.history: List[ReActStep] = []
        self.conversation = ConversationHistory()

    def reset(self) -> None:
        """Reset the reasoning loop state."""
        self.history = []
        self.conversation.clear()

    async def reason_and_act(
        self,
        context: "AgentContext",
        goal: str,
        available_actions: List[str],
        action_executor: Optional[Callable[[str, Dict], str]] = None,
        agent_identity: str = "agent_unknown"
    ) -> ReActResult:
        """
        Execute ReAct loop until goal achieved or max iterations.

        Args:
            context: Current agent context
            goal: The goal to achieve
            available_actions: List of available action names
            action_executor: Optional function to execute actions
            agent_identity: Agent identity for credential injection

        Returns:
            ReActResult with final decision and reasoning trace
        """
        self.history = []

        for i in range(self.max_iterations):
            step_num = i + 1
            logger.info(f"ReAct iteration {step_num}/{self.max_iterations}")

            # Generate thought and action
            try:
                thought, action, action_input = await self._generate_step(
                    context=context,
                    goal=goal,
                    available_actions=available_actions,
                    agent_identity=agent_identity
                )
            except Exception as e:
                logger.error(f"ReAct generation failed: {e}")
                return ReActResult(
                    final_thought=f"Error generating reasoning: {e}",
                    final_action="error",
                    confidence=0.0,
                    reasoning_trace=self.history,
                    success=False,
                    error=str(e)
                )

            # Create step (observation filled after action)
            step = ReActStep(
                step_number=step_num,
                thought=thought,
                action=action,
                action_input=action_input
            )

            # Check for completion
            if action.upper() == "FINISH":
                step.observation = "Goal achieved. Terminating reasoning loop."
                self.history.append(step)

                # Calculate confidence based on reasoning quality
                confidence = self._calculate_confidence()

                return ReActResult(
                    final_thought=thought,
                    final_action="complete",
                    confidence=confidence,
                    reasoning_trace=self.history,
                    success=True
                )

            # Execute action if executor provided
            if action_executor and action in available_actions:
                try:
                    observation = action_executor(action, action_input or {})
                    step.observation = observation
                except Exception as e:
                    step.observation = f"Action failed: {e}"
            else:
                step.observation = f"Action '{action}' acknowledged (no executor)"

            self.history.append(step)

            # Add to conversation for context
            self.conversation.add_message("assistant", step.to_prompt_format())

        # Max iterations reached
        final_thought = self.history[-1].thought if self.history else "No reasoning performed"
        final_action = self.history[-1].action if self.history else "none"

        return ReActResult(
            final_thought=final_thought,
            final_action=final_action or "max_iterations",
            confidence=self._calculate_confidence() * 0.7,  # Penalize for not finishing
            reasoning_trace=self.history,
            success=False,
            error="Max iterations reached without completing goal"
        )

    async def _generate_step(
        self,
        context: "AgentContext",
        goal: str,
        available_actions: List[str],
        agent_identity: str
    ) -> tuple:
        """Generate a single reasoning step using LLM."""

        # Format previous steps
        previous_steps = ""
        if self.history:
            previous_steps = "\n\n".join(
                step.to_prompt_format() for step in self.history
            )
        else:
            previous_steps = "This is the first reasoning step."

        # Format available actions
        actions_list = "\n".join(f"- {action}" for action in available_actions)
        actions_list += "\n- FINISH (use when goal is achieved)"

        # Build context summary
        context_summary = self._build_context_summary(context)

        # Build prompt
        prompt = self.REACT_PROMPT_TEMPLATE.format(
            goal=goal,
            available_actions=actions_list,
            context_summary=context_summary,
            previous_steps=previous_steps,
            conversation_history=self.conversation.format_for_prompt()
        )

        # Generate response
        if hasattr(self.llm, 'generate'):
            response = self.llm.generate(
                prompt,
                temperature=0.3,  # Lower temperature for reasoning
                agent_identity=agent_identity
            )
        else:
            # Fallback for testing
            response = "Thought: Analyzing context.\nAction: FINISH\nAction Input: none"

        # Parse response
        thought, action, action_input = self._parse_response(response)

        return thought, action, action_input

    def _parse_response(self, response: str) -> tuple:
        """Parse LLM response into thought, action, action input."""
        thought = ""
        action = ""
        action_input = None

        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line.lower().startswith("thought:"):
                thought = line[8:].strip()
            elif line.lower().startswith("action:"):
                action = line[7:].strip()
            elif line.lower().startswith("action input:"):
                input_str = line[13:].strip()
                if input_str.lower() != "none":
                    try:
                        import json
                        action_input = json.loads(input_str)
                    except json.JSONDecodeError:
                        action_input = {"raw": input_str}

        # Defaults
        if not thought:
            thought = "Continuing with task."
        if not action:
            action = "FINISH"

        return thought, action, action_input

    def _build_context_summary(self, context: "AgentContext") -> str:
        """Build a summary of current context for the prompt."""
        parts = []

        if context.product_data:
            parts.append(f"Product: {context.product_data.name}")
        else:
            parts.append("Product: Not loaded")

        if context.comparison_data:
            parts.append(f"Comparison Product: {context.comparison_data.name}")
        else:
            parts.append("Comparison Product: Not loaded")

        if context.analysis_results:
            parts.append("Analysis: Complete")
            if context.analysis_results.benefits:
                parts.append(f"  Benefits: {len(context.analysis_results.benefits)} found")
        else:
            parts.append("Analysis: Not started")

        parts.append(f"Validated: {'Yes' if context.is_valid else 'No'}")

        if context.validation_errors:
            parts.append(f"Errors: {', '.join(context.validation_errors)}")

        if context.generated_questions:
            parts.append(f"Questions Generated: {len(context.generated_questions)}")

        return "\n".join(parts)

    def _calculate_confidence(self) -> float:
        """Calculate confidence based on reasoning quality."""
        if not self.history:
            return 0.0

        base_confidence = 0.5

        # More steps with observations = more confidence
        steps_with_obs = sum(1 for s in self.history if s.observation)
        base_confidence += 0.1 * min(3, steps_with_obs)

        # Successful completion = high confidence
        if self.history and self.history[-1].action and \
           self.history[-1].action.upper() == "FINISH":
            base_confidence += 0.2

        # Penalize for errors in observations
        error_steps = sum(1 for s in self.history
                         if s.observation and "fail" in s.observation.lower())
        base_confidence -= 0.1 * error_steps

        return max(0.0, min(1.0, base_confidence))

    def get_reasoning_summary(self) -> str:
        """Get a summary of the reasoning process."""
        if not self.history:
            return "No reasoning performed."

        thoughts = [s.thought for s in self.history]
        actions = [s.action for s in self.history if s.action]

        return (
            f"Reasoning steps: {len(self.history)}\n"
            f"Final thought: {thoughts[-1] if thoughts else 'None'}\n"
            f"Actions taken: {', '.join(actions) if actions else 'None'}"
        )


# Factory function
def create_react_loop(
    llm_client: Any = None,
    max_iterations: int = 5
) -> ReActLoop:
    """Create a ReAct loop with optional LLM client."""
    if llm_client is None:
        try:
            from skincare_agent_system.infrastructure.llm_client import LLMClient
            llm_client = LLMClient()
        except Exception:
            llm_client = None

    return ReActLoop(llm_client=llm_client, max_iterations=max_iterations)
