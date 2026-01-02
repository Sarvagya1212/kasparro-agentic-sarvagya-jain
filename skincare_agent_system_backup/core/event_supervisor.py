"""
Event Supervisor: Event-driven orchestration replacing the sequential loop.
Supervisor pattern - watches events and coordinates agents without driving execution.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.models import AgentContext
    from skincare_agent_system.core.proposals import (
        AsyncEventBus,
        Event,
        GoalManager,
        ProposalSystem,
    )

logger = logging.getLogger("EventSupervisor")


class SupervisorState(Enum):
    """State of the event supervisor."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class EventRule:
    """
    Rule that maps events to actions.

    When an event matching the rule is received,
    the specified action is executed.
    """

    event_type: str
    action: str  # What to do: "collect_proposals", "execute_agent", "complete", etc.
    condition: Optional[Callable[["Event", "AgentContext"], bool]] = None
    target_agent: Optional[str] = None
    priority: int = 5
    description: str = ""


@dataclass
class SupervisorEvent:
    """Internal supervisor event record."""

    event_type: str
    source: str
    action_taken: str
    timestamp: str
    success: bool
    details: Optional[str] = None


class EventSupervisor:
    """
    Event-driven supervisor replacing the loop-based orchestrator.

    Key differences from Orchestrator:
    1. Does NOT drive execution with a loop
    2. Responds to events from agents
    3. Uses goals for completion detection (not step count)
    4. Coordinates via event rules, not sequential calls

    The supervisor:
    1. Watches for events on the event bus
    2. Applies event rules to determine actions
    3. Coordinates agent execution based on events
    4. Detects completion based on goal achievement
    """

    def __init__(
        self,
        event_bus: "AsyncEventBus",
        proposal_system: "ProposalSystem",
        goal_manager: "GoalManager",
    ):
        self._event_bus = event_bus
        self._proposal_system = proposal_system
        self._goal_manager = goal_manager
        self._rules: List[EventRule] = []
        self._agents: Dict[str, "BaseAgent"] = {}
        self._context: Optional["AgentContext"] = None
        self._state = SupervisorState.IDLE
        self._event_history: List[SupervisorEvent] = []
        self._completion_event: Optional[asyncio.Event] = None
        self._error: Optional[str] = None

        # Initialize default rules
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Set up default event rules."""
        self._rules = [
            # Data loaded -> Collect proposals for next step
            EventRule(
                event_type="data_loaded",
                action="collect_proposals",
                description="Collect proposals after data is loaded",
            ),
            # Synthetic data generated -> Collect proposals
            EventRule(
                event_type="synthetic_data_generated",
                action="collect_proposals",
                description="Collect proposals after synthetic data",
            ),
            # Analysis complete -> Collect proposals
            EventRule(
                event_type="analysis_complete",
                action="collect_proposals",
                description="Collect proposals after analysis",
            ),
            # Validation passed -> Move to generation
            EventRule(
                event_type="validation_passed",
                action="collect_proposals",
                description="Collect proposals after validation",
            ),
            # Validation failed -> Retry analysis
            EventRule(
                event_type="validation_failed",
                action="retry_analysis",
                description="Retry analysis after validation failure",
            ),
            # Generation complete -> Verify
            EventRule(
                event_type="generation_complete",
                action="collect_proposals",
                description="Collect proposals after generation",
            ),
            # Verification complete -> Check goals
            EventRule(
                event_type="verification_complete",
                action="check_completion",
                description="Check if workflow is complete",
            ),
            # Error occurred -> Handle error
            EventRule(
                event_type="error_occurred",
                action="handle_error",
                description="Handle error event",
            ),
            # Agent selected -> Execute agent
            EventRule(
                event_type="agent_selected",
                action="execute_agent",
                description="Execute the selected agent",
            ),
            # Goal achieved -> Check if all goals done
            EventRule(
                event_type="goal_achieved",
                action="check_completion",
                description="Check all goals after one achieved",
            ),
        ]

    def add_rule(self, rule: EventRule) -> None:
        """Add a custom event rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"Added event rule: {rule.event_type} -> {rule.action}")

    def remove_rule(self, event_type: str) -> None:
        """Remove rules for an event type."""
        self._rules = [r for r in self._rules if r.event_type != event_type]

    def register_agent(self, agent: "BaseAgent") -> None:
        """Register an agent with the supervisor."""
        self._agents[agent.name] = agent
        self._proposal_system.register_agent(agent.name, agent)
        agent.set_event_bus(self._event_bus)
        logger.info(f"Registered agent: {agent.name}")

    async def start(
        self, initial_context: "AgentContext", initial_event: Optional["Event"] = None
    ) -> "AgentContext":
        """
        Start the event-driven supervision.

        Unlike the orchestrator's run(), this:
        1. Sets up event subscriptions
        2. Fires initial event if provided
        3. Watches for events and responds
        4. Returns when goals are achieved

        Args:
            initial_context: Starting context
            initial_event: Optional event to trigger workflow start

        Returns:
            Final context after workflow completes
        """
        logger.info("EventSupervisor starting...")
        self._context = initial_context
        self._state = SupervisorState.RUNNING
        self._completion_event = asyncio.Event()
        self._error = None

        # Subscribe to all relevant events
        self._subscribe_to_events()

        # Start the event bus if async
        if hasattr(self._event_bus, "start"):
            await self._event_bus.start()

        try:
            # Fire initial event or start with proposal collection
            if initial_event:
                await self._handle_event(initial_event)
            else:
                await self._collect_and_execute_proposals()

            # Wait for completion (with timeout)
            try:
                await asyncio.wait_for(
                    self._completion_event.wait(),
                    timeout=300.0,  # 5 minute max workflow time
                )
            except asyncio.TimeoutError:
                logger.warning("Workflow timed out after 5 minutes")
                self._state = SupervisorState.ERROR
                self._error = "Workflow timeout"

        except Exception as e:
            logger.error(f"Supervisor error: {e}")
            self._state = SupervisorState.ERROR
            self._error = str(e)

        finally:
            # Stop the event bus
            if hasattr(self._event_bus, "stop"):
                await self._event_bus.stop()

        if self._state == SupervisorState.COMPLETED:
            logger.info("Workflow completed successfully")
        else:
            logger.warning(f"Workflow ended with state: {self._state.value}")

        return self._context

    async def stop(self) -> None:
        """Stop the supervisor."""
        self._state = SupervisorState.COMPLETING
        if self._completion_event:
            self._completion_event.set()

    def _subscribe_to_events(self) -> None:
        """Subscribe to all event types in rules."""
        event_types = set(r.event_type for r in self._rules)

        for event_type in event_types:
            self._event_bus.subscribe(
                event_type,
                lambda e, et=event_type: asyncio.create_task(self._handle_event(e)),
            )
            logger.debug(f"Subscribed to event: {event_type}")

    async def _handle_event(self, event: "Event") -> None:
        """
        Handle an incoming event by applying matching rules.
        """
        if self._state not in [SupervisorState.RUNNING]:
            return

        logger.info(f"Handling event: {event.type} from {event.source}")

        # Find matching rules
        matching_rules = [r for r in self._rules if r.event_type == event.type]

        if not matching_rules:
            logger.debug(f"No rules match event: {event.type}")
            return

        for rule in matching_rules:
            # Check condition if present
            if rule.condition and not rule.condition(event, self._context):
                continue

            # Execute action
            success = await self._execute_action(rule, event)

            # Record
            self._event_history.append(
                SupervisorEvent(
                    event_type=event.type,
                    source=event.source,
                    action_taken=rule.action,
                    timestamp=datetime.now().isoformat(),
                    success=success,
                )
            )

            # Only execute first matching rule
            break

    async def _execute_action(self, rule: EventRule, event: "Event") -> bool:
        """Execute an action from an event rule."""
        action = rule.action

        try:
            if action == "collect_proposals":
                await self._collect_and_execute_proposals()

            elif action == "execute_agent":
                agent_name = rule.target_agent or event.payload.get("agent")
                if agent_name:
                    await self._execute_agent(agent_name)

            elif action == "check_completion":
                await self._check_completion()

            elif action == "retry_analysis":
                # Re-run delegator
                if "DelegatorAgent" in self._agents:
                    await self._execute_agent("DelegatorAgent")

            elif action == "handle_error":
                self._handle_error(event)

            elif action == "complete":
                self._state = SupervisorState.COMPLETED
                self._completion_event.set()

            else:
                logger.warning(f"Unknown action: {action}")
                return False

            return True

        except Exception as e:
            logger.error(f"Action {action} failed: {e}")
            return False

    async def _collect_and_execute_proposals(self) -> None:
        """Collect proposals and execute best agent."""
        # Collect proposals
        if hasattr(self._proposal_system, "collect_proposals_async"):
            proposals = await self._proposal_system.collect_proposals_async(
                self._context
            )
        else:
            proposals = self._proposal_system.collect_proposals(self._context)

        if not proposals:
            logger.info("No proposals - checking if complete")
            await self._check_completion()
            return

        # Log proposals
        for p in proposals:
            self._context.log_decision(
                "Supervisor",
                f"Proposal: {p.agent_name} -> {p.action} (conf: {p.confidence:.2f})",
            )

        # Select best
        best = self._proposal_system.select_best_proposal(
            proposals, strategy="priority_then_confidence"
        )

        if best:
            self._context.log_decision(
                "Supervisor", f"Selected: {best.agent_name} - {best.reason}"
            )
            await self._execute_agent(best.agent_name)
        else:
            await self._check_completion()

    async def _execute_agent(self, agent_name: str) -> None:
        """Execute a specific agent."""
        agent = self._agents.get(agent_name)
        if not agent:
            logger.error(f"Agent not found: {agent_name}")
            return

        logger.info(f"Executing agent: {agent_name}")
        self._context.log_step(f"Running {agent_name}")

        try:
            # Execute agent
            if hasattr(agent, "run_async"):
                result = await agent.run_async(self._context, None)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, agent.run, self._context, None
                )

            # Update context
            self._context = result.context

            # Agent publishes its own completion event
            # The event will trigger the next action via rules

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            # Publish error event
            from skincare_agent_system.core.proposals import Event, EventType

            await self._event_bus.publish(
                Event(
                    type=EventType.ERROR_OCCURRED,
                    source=agent_name,
                    payload={"error": str(e)},
                )
            )

    async def _check_completion(self) -> None:
        """Check if workflow is complete."""
        # Update goal progress
        self._goal_manager.update_progress(self._context)

        if self._goal_manager.all_goals_achieved(self._context):
            logger.info("All goals achieved - completing workflow")
            self._state = SupervisorState.COMPLETED
            if self._completion_event:
                self._completion_event.set()
        else:
            # Not done yet - collect more proposals
            pending = self._goal_manager.get_pending_goals()
            logger.info(f"Goals pending: {len(pending)}")

            # Don't infinite loop - check if we can make progress
            proposals = self._proposal_system.collect_proposals(self._context)
            if proposals:
                await self._collect_and_execute_proposals()
            else:
                # No proposals and goals not met - stuck
                logger.warning("No proposals available but goals not met")
                self._state = SupervisorState.ERROR
                self._error = "Stuck: no proposals but goals incomplete"
                if self._completion_event:
                    self._completion_event.set()

    def _handle_error(self, event: "Event") -> None:
        """Handle error event."""
        error_msg = event.payload.get("error", "Unknown error")
        logger.error(f"Error from {event.source}: {error_msg}")

        self._context.log_decision("Supervisor", f"ERROR: {event.source} - {error_msg}")

        # Don't stop on first error - let goals determine completion
        # But track it
        if not hasattr(self._context, "errors"):
            self._context.errors = []
        self._context.errors.append(
            {
                "source": event.source,
                "message": error_msg,
                "timestamp": datetime.now().isoformat(),
            }
        )

    @property
    def state(self) -> SupervisorState:
        return self._state

    @property
    def error(self) -> Optional[str]:
        return self._error

    def get_event_history(self) -> List[SupervisorEvent]:
        """Get history of handled events."""
        return self._event_history.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get supervisor statistics."""
        return {
            "state": self._state.value,
            "registered_agents": len(self._agents),
            "event_rules": len(self._rules),
            "events_handled": len(self._event_history),
            "successful_actions": sum(1 for e in self._event_history if e.success),
            "error": self._error,
        }


def create_event_supervisor(
    event_bus: Optional["AsyncEventBus"] = None,
    proposal_system: Optional["ProposalSystem"] = None,
    goal_manager: Optional["GoalManager"] = None,
) -> EventSupervisor:
    """Create and configure an event supervisor."""
    from skincare_agent_system.core.proposals import (
        AsyncEventBus,
        GoalManager,
        ProposalSystem,
    )

    if event_bus is None:
        event_bus = AsyncEventBus()

    if proposal_system is None:
        proposal_system = ProposalSystem()

    if goal_manager is None:
        goal_manager = GoalManager()

    return EventSupervisor(
        event_bus=event_bus, proposal_system=proposal_system, goal_manager=goal_manager
    )
