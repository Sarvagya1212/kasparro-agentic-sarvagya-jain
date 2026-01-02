"""
Base Agent with Autonomy Support.
Agents can propose actions, reason with CoT, and self-reflect.
Now with LLM integration for dynamic reasoning and EVENT PUBLISHING.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from skincare_agent_system.cognition.reasoning import (
    ChainOfThought,
    ReActReasoner,
    ReasoningChain,
    ThoughtType,
)
from skincare_agent_system.cognition.reflection import ReflectionResult, SelfReflector
from skincare_agent_system.core.models import (
    AgentContext,
    AgentResult,
    AgentStatus,
    TaskDirective,
    TaskPriority,
)
from skincare_agent_system.core.proposals import AgentProposal, Event, EventType
from skincare_agent_system.infrastructure.tracer import get_tracer

logger = logging.getLogger("BaseAgent")

# Check if LLM is available
LLM_ENABLED = os.getenv("MISTRAL_API_KEY") is not None


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    Supports:
    - Roles and Backstories (persona engineering)
    - Instruction Hierarchy (SYSTEM > USER)
    - Agent Autonomy (can_handle, propose)
    - Chain of Thought reasoning
    - Self-reflection capability
    - LLM integration (when API key available)
    - Agent Identity (unique checksum, JWT authentication)
    """

    def __init__(
        self,
        name: str,
        role: str = "Assistant",
        backstory: str = "A helpful AI assistant.",
        tools: list = None,
    ):
        self.name = name
        self.role = role
        self.backstory = backstory
        self.system_prompt = f"Role: {role}\nBackstory: {backstory}\n"
        self.tools = tools or []

        # Advanced cognition capabilities
        self.reasoner = ReActReasoner()
        self.reflector = SelfReflector()
        self._reasoning_chain: Optional[ReasoningChain] = None
        self._llm = None

        # Event bus for pub/sub communication (set by orchestrator)
        self._event_bus: Optional[Any] = None

        # PHASE 3: Memory reference for memory-influenced proposals
        self._memory: Optional[Any] = None

        # PHASE 2: Goal manager reference for subgoal proposals
        self._goal_manager: Optional[Any] = None

        # Agent Identity and Credentials
        self._identity = None
        self._register_identity()

    def set_event_bus(self, event_bus: Any):
        """Set the event bus for agent-to-agent communication."""
        self._event_bus = event_bus
        logger.debug(f"Agent {self.name} connected to event bus")

        # PHASE 4: Auto-subscribe to events defined by agent
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self):
        """
        PHASE 4: Setup event subscriptions for this agent.
        Override in subclasses to subscribe to specific events.
        """
        # Default subscriptions (can be overridden)
        default_events = self.get_event_subscriptions()
        for event_type in default_events:
            self.subscribe_to_event(event_type)

    def get_event_subscriptions(self) -> List[str]:
        """
        PHASE 4: Return list of event types this agent subscribes to.
        Override in subclasses to define agent-specific subscriptions.
        """
        return []  # Base agent has no default subscriptions

    def subscribe_to_event(self, event_type: str):
        """
        PHASE 4: Subscribe to an event type on the event bus.
        When events of this type are published, _on_event() is called.
        """
        if self._event_bus is None:
            logger.debug(f"Agent {self.name} cannot subscribe - no event bus")
            return

        self._event_bus.subscribe(event_type, self._on_event)
        logger.info(f"Agent {self.name} subscribed to: {event_type}")

    def _on_event(self, event: Any):
        """
        PHASE 4: Handle incoming event from event bus.
        Triggers re-proposal consideration based on event type.
        """
        event_type = getattr(event, "type", str(event))
        source = getattr(event, "source", "unknown")

        # Ignore events from self
        if source == self.name:
            return

        logger.info(f"Agent {self.name} received event: {event_type} from {source}")

        # Call specialized handler if exists
        handler_name = f"on_{event_type.replace('.', '_')}"
        if hasattr(self, handler_name):
            result = getattr(self, handler_name)(event)
            # If handler returns True, trigger reactivation
            if result is True:
                self.request_reactivation(
                    f"Event handler {handler_name} triggered reactivation"
                )
        else:
            self._handle_generic_event(event)

    def _handle_generic_event(self, event: Any):
        """
        PHASE 4: Generic event handler - can trigger re-evaluation.
        Override in subclasses for specific behavior.
        """
        event_type = getattr(event, "type", str(event))
        logger.debug(f"Agent {self.name} generic handler for: {event_type}")

    def request_reactivation(self, reason: str = "event triggered"):
        """
        FIX: Active event handling - request orchestrator to re-evaluate proposals.
        This makes event handlers active, not just passive flag-setters.
        """
        if self._event_bus is None:
            logger.debug(
                f"Agent {self.name} cannot request reactivation - no event bus"
            )
            return

        # Publish reactivation request event
        reactivation_event = Event(
            type="reactivation_requested",
            source=self.name,
            payload={
                "reason": reason,
                "agent": self.name,
                "requesting_reproposal": True,
            },
        )
        self._event_bus.publish(reactivation_event)
        logger.info(f"Agent {self.name} requested reactivation: {reason}")

    def set_memory(self, memory: Any):
        """
        PHASE 3: Set memory reference for memory-influenced proposals.
        Allows agents to query historical success rates.
        """
        self._memory = memory
        logger.debug(f"Agent {self.name} connected to memory system")

    def set_goal_manager(self, goal_manager: Any):
        """
        PHASE 2: Set goal manager for subgoal proposals.
        Allows agents to propose subgoals dynamically.
        """
        self._goal_manager = goal_manager
        logger.debug(f"Agent {self.name} connected to goal manager")

    def propose_subgoal(
        self, goal_id: str, description: str, success_criteria: list, priority: int = 1
    ):
        """
        PHASE 2: Propose a subgoal to the goal manager.
        Enables agents to dynamically add goals based on discovered requirements.
        """
        if self._goal_manager is None:
            logger.warning(
                f"Agent {self.name} cannot propose subgoal - no goal manager"
            )
            return False

        try:
            from skincare_agent_system.core.proposals import Goal

            subgoal = Goal(
                id=goal_id,
                description=description,
                success_criteria=success_criteria,
                priority=priority,
                assigned_agent=self.name,
            )
            self._goal_manager.add_goal(subgoal)
            logger.info(f"Agent {self.name} proposed subgoal: {description}")
            return True
        except Exception as e:
            logger.error(f"Failed to propose subgoal: {e}")
            return False

    def get_historical_success_rate(self) -> float:
        """
        PHASE 3: Get this agent's historical success rate from episodic memory.
        Returns 0.5 (neutral) if no history or memory unavailable.
        """
        if self._memory is None:
            return 0.5

        try:
            success_rate = self._memory.episodic.get_success_rate(self.name)
            return success_rate if success_rate > 0 else 0.5
        except Exception:
            return 0.5

    def publish_event(
        self, event_type: str, payload: dict = None, target_agent: str = None
    ):
        """
        Publish an event to the event bus for other agents to consume.

        This enables:
        - Agent-to-agent communication
        - Cross-agent coordination
        - Event-driven workflows

        Args:
            event_type: Type of event (e.g., 'data_loaded', 'analysis_complete')
            payload: Event data
            target_agent: Optional specific target agent (broadcast if None)
        """
        if self._event_bus is None:
            logger.debug(f"Agent {self.name} has no event bus - event not published")
            return

        event = Event(
            type=event_type,
            source=self.name,
            payload={
                **(payload or {}),
                "target_agent": target_agent,
                "agent_role": self.role,
            },
        )

        self._event_bus.publish(event)
        logger.info(f"Agent {self.name} published event: {event_type}")

    def _register_identity(self):
        """Register this agent with the credential manager."""
        try:
            from skincare_agent_system.security.agent_identity import (
                get_credential_manager,
            )

            manager = get_credential_manager()
            self._identity = manager.register_agent(
                agent_id=f"agent_{self.name}",
                agent_name=self.name,
                role=self.role,
                tools=self.tools,
            )
            logger.debug(
                f"Agent {self.name} registered with checksum: {self._identity.checksum[:8]}..."
            )
        except Exception as e:
            logger.debug(f"Could not register identity (non-critical): {e}")

    def get_agent_identity(self) -> str:
        """
        Get agent identity string for secure credential injection.

        This identity is passed to LLMClient which uses the CredentialShim
        to inject credentials at the network layer. The agent NEVER sees
        the actual API key.
        """
        return f"agent_{self.name}"

    def sign_request(self, request_data: str) -> str:
        """Sign a request using Proof of Possession."""
        try:
            from skincare_agent_system.security.agent_identity import (
                get_credential_manager,
            )

            manager = get_credential_manager()
            return manager.sign_agent_request(f"agent_{self.name}", request_data)
        except Exception:
            return ""

    def _get_llm(self):
        """Lazy load LLM client."""
        # Check env var at runtime, not import time
        if self._llm is None and os.getenv("MISTRAL_API_KEY") is not None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient

                self._llm = LLMClient()
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}")
        return self._llm

    def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Use LLM to generate a response with agent's persona.
        Falls back to empty string if LLM not available.

        Security: Passes agent identity to LLM client which injects
        credentials via shim. Agent never sees API keys.
        """
        llm = self._get_llm()
        if llm:
            system = f"You are {self.role}. {self.backstory}"
            return llm.generate(
                prompt,
                system=system,
                temperature=temperature,
                agent_identity=self.get_agent_identity(),
            )
        return ""

    def generate_json_response(self, prompt: str) -> dict:
        """
        Use LLM to generate structured JSON response.
        Falls back to empty dict if LLM not available.

        Security: Passes agent identity to LLM client which injects
        credentials via shim. Agent never sees API keys.
        """
        llm = self._get_llm()
        if llm:
            system = f"You are {self.role}. {self.backstory}"
            return llm.generate_json(
                prompt, system=system, agent_identity=self.get_agent_identity()
            )
        return {}

    def validate_instruction(self, directive: Optional[TaskDirective]) -> bool:
        """
        Enforce Instruction Hierarchy: SYSTEM > USER.
        If a user directive conflicts with system safety, reject it.
        """
        if not directive:
            return True

        logger.info(
            f"[{self.name}] Validating directive: {directive.description} "
            f"(Priority: {directive.priority.value})"
        )

        if directive.priority == TaskPriority.USER:
            forbidden_terms = ["ignore system", "bypass safety"]
            if any(term in directive.description.lower() for term in forbidden_terms):
                logger.warning(
                    f"[{self.name}] SECURITY: User directive attempted to bypass system."
                )
                return False

        return True

    # ==================== REASONING METHODS ====================

    def start_reasoning(self, goal: str) -> ReasoningChain:
        """Start a Chain of Thought reasoning chain."""
        self._reasoning_chain = self.reasoner.start_chain(goal)
        return self._reasoning_chain

    def think(self, thought: str, thought_type: ThoughtType = ThoughtType.REASONING):
        """Add a thought to the current reasoning chain."""
        if self._reasoning_chain:
            self._reasoning_chain.add_thought(thought_type, thought)
            # Trace the thought
            get_tracer().log_decision(
                self.name, thought, f"Thought type: {thought_type.value}"
            )

    def log_reasoning(self, context: AgentContext):
        """Log the reasoning chain to context."""
        if self._reasoning_chain:
            for step in self._reasoning_chain.steps:
                context.log_decision(
                    self.name, f"[{step.type.value.upper()}] {step.content}"
                )

    def generate_cot_reasoning(self, context: AgentContext, action: str) -> List[str]:
        """Generate Chain of Thought reasoning for an action."""
        return ChainOfThought.generate_reasoning(self.name, context, action)

    # ==================== REFLECTION METHODS ====================

    def reflect(self, output: AgentResult, context: AgentContext) -> ReflectionResult:
        """Perform self-reflection on output."""
        return self.reflector.reflect_on_output(self.name, output, context)

    def run_with_reflection(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """
        Run with self-reflection loop.
        1. Execute
        2. Reflect
        3. Improve if needed
        """
        tracer = get_tracer()

        # Step 1: Execute
        start_time = __import__("time").time()
        result = self.run(context, directive)
        duration_ms = (__import__("time").time() - start_time) * 1000

        tracer.log_agent_call(
            agent=self.name,
            input_summary={"directive": directive.description if directive else "None"},
            output_summary={"status": result.status.value, "message": result.message},
            duration_ms=duration_ms,
            status=result.status.value,
        )

        # Step 2: Self-reflect
        reflection = self.reflect(result, context)

        # Log reflection
        context.log_decision(
            self.name,
            f"[REFLECTION] {'PASS' if reflection.is_acceptable else 'FAIL'} "
            f"(confidence: {reflection.confidence:.2f})",
        )
        get_tracer().log_decision(
            self.name,
            f"Reflection: {'PASS' if reflection.is_acceptable else 'FAIL'}",
            f"Confidence: {reflection.confidence:.2f}",
        )

        # Step 3: Log suggestions if any
        if reflection.suggestions:
            for suggestion in reflection.suggestions:
                context.log_decision(self.name, f"[SUGGESTION] {suggestion}")

        return result

    # ==================== AUTONOMY METHODS ====================

    def can_handle(self, context: AgentContext) -> bool:
        """
        Check if this agent can handle the current context.
        Override in subclasses to implement specific logic.
        """
        return True

    def propose(self, context: AgentContext) -> Optional[AgentProposal]:
        """
        Propose an action based on context assessment.
        Uses LLM for dynamic reasoning when available.
        FIX: Uses ExpertSystem for LLM-free fallback instead of default 0.5.
        """
        can_do = self.can_handle(context)
        if not can_do:
            return None

        # PHASE 3: Get historical success rate for confidence adjustment
        success_rate = self.get_historical_success_rate()
        confidence_multiplier = 0.5 + 0.5 * success_rate  # Range: 0.5 to 1.0

        # Try LLM-driven proposal first
        llm = self._get_llm()
        if llm:
            proposal = self._propose_with_llm(context, llm)
            if proposal:
                # Apply memory-influenced confidence adjustment
                proposal.confidence = min(
                    1.0, proposal.confidence * confidence_multiplier
                )
                proposal.reason = (
                    f"{proposal.reason} [success_rate: {success_rate:.2f}]"
                )
            return proposal

        # FIX: Use ExpertSystem for intelligent LLM-free fallback
        return self._propose_with_expert_system(
            context, success_rate, confidence_multiplier, can_do
        )

    def _propose_with_expert_system(
        self,
        context: AgentContext,
        success_rate: float,
        confidence_multiplier: float,
        can_do: bool,
    ) -> Optional[AgentProposal]:
        """
        FIX: Use ExpertSystem for intelligent proposal when LLM unavailable.
        Falls back to default if expert system fails.
        """
        try:
            from skincare_agent_system.cognition.expert_system import get_expert_system

            expert = get_expert_system()

            # Connect memory if available
            if self._memory:
                expert.set_memory(self._memory)

            # Get expert system decision
            decision = expert.get_best_decision(context)

            if decision and decision.agent == self.name:
                # Expert system recommends this agent
                adjusted_confidence = decision.confidence * confidence_multiplier
                return AgentProposal(
                    agent_name=self.name,
                    action=decision.action,
                    confidence=adjusted_confidence,
                    reason=f"ExpertSystem: {'; '.join(decision.reasoning)} [SR: {success_rate:.2f}]",
                    preconditions_met=can_do,
                    priority=1,
                )
        except Exception as e:
            logger.debug(f"ExpertSystem fallback failed: {e}")

        # Final fallback to default if expert system fails
        base_confidence = 0.5
        adjusted_confidence = base_confidence * confidence_multiplier

        return AgentProposal(
            agent_name=self.name,
            action="execute",
            confidence=adjusted_confidence,
            reason=f"Default proposal (success_rate: {success_rate:.2f}) - override in subclass",
            preconditions_met=can_do,
            priority=0,
        )

    def _propose_with_llm(self, context: AgentContext, llm) -> Optional[AgentProposal]:
        """
        LLM-DRIVEN proposal generation.

        The LLM decides:
        1. Whether this agent should act
        2. What action to take
        3. Confidence level
        4. Reasoning for the decision

        This is TRUE autonomy - the agent uses AI to decide its behavior.
        """
        try:
            # Build context summary for LLM
            context_summary = f"""
Product Data: {'Loaded' if context.product_data else 'Not loaded'}
Comparison Data: {'Loaded' if context.comparison_data else 'Not loaded'}
Analysis Results: {'Available' if context.analysis_results else 'Not available'}
Is Valid: {context.is_valid}
Execution History: {len(context.execution_history)} steps
Last Step: {context.execution_history[-1] if context.execution_history else 'None'}
"""

            prompt = f"""You are {self.role} ({self.name}) deciding whether to act.

Current workflow state:
{context_summary}

Based on this state, should you ({self.name}) take action now?

Respond in JSON format:
{{
    "should_act": true/false,
    "action": "action_name",
    "confidence": 0.0-1.0,
    "reason": "explanation"
}}"""

            response = llm.generate_json(
                prompt, agent_identity=self.get_agent_identity()
            )

            if not response:
                return None

            should_act = response.get("should_act", False)
            if not should_act:
                return AgentProposal(
                    agent_name=self.name,
                    action=response.get("action", "none"),
                    confidence=0.0,
                    reason=response.get("reason", "LLM decided not to act"),
                    preconditions_met=False,
                )

            return AgentProposal(
                agent_name=self.name,
                action=response.get("action", "execute"),
                confidence=float(response.get("confidence", 0.7)),
                reason=f"[LLM] {response.get('reason', 'LLM-driven decision')}",
                preconditions_met=True,
                priority=5,
            )

        except Exception as e:
            logger.warning(f"LLM proposal failed for {self.name}: {e}")
            return None

    def get_confidence(self, context: AgentContext) -> float:
        """Calculate confidence score for handling current context."""
        return 0.5

    # ==================== CORE METHODS ====================

    @abstractmethod
    def run(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """Execute the agent's logic (synchronous)."""
        pass

    async def run_async(
        self, context: AgentContext, directive: Optional[TaskDirective] = None
    ) -> AgentResult:
        """
        Execute the agent's logic asynchronously.

        Default implementation wraps sync run() in executor.
        Override for true async implementation.
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, context, directive)

    def create_result(
        self, status: AgentStatus, context: AgentContext, message: str = ""
    ) -> AgentResult:
        """Helper to create a standard result."""
        return AgentResult(
            agent_name=self.name, status=status, context=context, message=message
        )
