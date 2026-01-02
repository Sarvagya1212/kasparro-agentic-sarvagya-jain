"""
Reactive Event System for Agent Autonomy.
Enables agents to react to events autonomously instead of waiting for orchestrator.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("EventSystem")


class EventType(Enum):
    """System-wide event types for agent communication."""
    
    # Data lifecycle
    DATA_LOADED = "data_loaded"
    SYNTHETIC_DATA_GENERATED = "synthetic_data_generated"
    
    # Analysis lifecycle
    ANALYSIS_STARTED = "analysis_started"
    BENEFITS_EXTRACTED = "benefits_extracted"
    USAGE_EXTRACTED = "usage_extracted"
    QUESTIONS_GENERATED = "questions_generated"
    COMPARISON_COMPLETE = "comparison_complete"
    ANALYSIS_COMPLETE = "analysis_complete"
    
    # Validation lifecycle
    VALIDATION_STARTED = "validation_started"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    
    # Generation lifecycle
    GENERATION_STARTED = "generation_started"
    GENERATION_COMPLETE = "generation_complete"
    
    # Error handling
    ERROR_OCCURRED = "error_occurred"
    RETRY_REQUESTED = "retry_requested"
    
    # Workflow control
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"


@dataclass
class Event:
    """Immutable event structure for agent communication."""
    
    type: EventType
    source_agent: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.correlation_id is None:
            import uuid
            self.correlation_id = str(uuid.uuid4())[:8]


@dataclass
class Subscription:
    """Subscription record for event handling."""
    
    agent_name: str
    handler: Callable[[Event], bool]
    priority: int = 0  # Higher = called first


class ReactiveEventBus:
    """
    Event bus with reactive subscriptions.
    
    Agents subscribe to events and can request re-proposal when events occur.
    This enables autonomous agent reactions without orchestrator control.
    """
    
    def __init__(self):
        self._subscriptions: Dict[EventType, List[Subscription]] = {}
        self._event_history: List[Event] = []
        self._max_history = 100
    
    def subscribe(
        self, 
        event_type: EventType, 
        handler: Callable[[Event], bool], 
        agent_name: str,
        priority: int = 0
    ):
        """
        Subscribe to events with automatic re-proposal triggering.
        
        Args:
            event_type: Event to subscribe to
            handler: Callback function (event) -> should_repropose: bool
            agent_name: Name of subscribing agent
            priority: Handler priority (higher = called first)
        """
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        
        subscription = Subscription(
            agent_name=agent_name,
            handler=handler,
            priority=priority
        )
        
        self._subscriptions[event_type].append(subscription)
        # Sort by priority (descending)
        self._subscriptions[event_type].sort(key=lambda s: -s.priority)
        
        logger.info(f"✓ {agent_name} subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, agent_name: str):
        """Unsubscribe agent from event type."""
        if event_type in self._subscriptions:
            self._subscriptions[event_type] = [
                s for s in self._subscriptions[event_type]
                if s.agent_name != agent_name
            ]
    
    def publish(self, event: Event) -> List[str]:
        """
        Publish event and trigger reactive handlers.
        
        Returns:
            List of agent names requesting re-proposal
        """
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        subscriptions = self._subscriptions.get(event.type, [])
        subscriber_count = len(subscriptions)
        
        logger.info(
            f"📢 Event {event.type.value} from {event.source_agent} "
            f"→ {subscriber_count} subscriber(s)"
        )
        
        repropose_requests = []
        
        for subscription in subscriptions:
            try:
                should_repropose = subscription.handler(event)
                if should_repropose:
                    repropose_requests.append(subscription.agent_name)
                    logger.debug(f"  ↳ {subscription.agent_name} requests re-proposal")
            except Exception as e:
                logger.error(
                    f"Handler error in {subscription.agent_name}: {e}"
                )
        
        if repropose_requests:
            logger.info(f"  → {len(repropose_requests)} agent(s) requesting re-proposal")
        
        return repropose_requests
    
    def get_history(self, event_type: Optional[EventType] = None) -> List[Event]:
        """Get event history, optionally filtered by type."""
        if event_type is None:
            return list(self._event_history)
        return [e for e in self._event_history if e.type == event_type]
    
    def get_last_event(self, event_type: EventType) -> Optional[Event]:
        """Get most recent event of a type."""
        history = self.get_history(event_type)
        return history[-1] if history else None
    
    def clear_history(self):
        """Clear event history."""
        self._event_history.clear()


# Global event bus instance
event_bus = ReactiveEventBus()


def get_event_bus() -> ReactiveEventBus:
    """Get the global event bus instance."""
    return event_bus


def publish_event(
    event_type: EventType,
    source_agent: str,
    data: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Convenience function to publish an event."""
    event = Event(
        type=event_type,
        source_agent=source_agent,
        data=data or {}
    )
    return event_bus.publish(event)
