"""
Lightweight Event Bus using Observer Pattern.
Non-blocking async logging for state changes.
"""

import json
import logging
from datetime import datetime
from threading import Thread
from typing import Any, Callable, Dict, List

logger = logging.getLogger("EventBus")


class EventBus:
    """
    Lightweight observer pattern for state change notifications.
    Non-blocking - logs asynchronously without impacting workflow.
    """

    _subscribers: List[Callable] = []
    _event_log: List[Dict[str, Any]] = []

    @classmethod
    def subscribe(cls, callback: Callable[[str, Dict], None]):
        """Add a subscriber callback."""
        cls._subscribers.append(callback)
        logger.debug(f"Subscriber added, total: {len(cls._subscribers)}")

    @classmethod
    def unsubscribe(cls, callback: Callable):
        """Remove a subscriber."""
        if callback in cls._subscribers:
            cls._subscribers.remove(callback)

    @classmethod
    def emit(cls, event: str, data: Dict[str, Any] = None, trace_id: str = None):
        """
        Emit event to all subscribers (non-blocking).
        """
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data or {},
            "trace_id": trace_id,
        }

        # Log event
        cls._event_log.append(event_data)
        logger.info(f"Event: {event}", extra={"trace_id": trace_id})

        # Notify subscribers asynchronously (non-blocking)
        for sub in cls._subscribers:
            Thread(target=sub, args=(event, event_data), daemon=True).start()

    @classmethod
    def get_events(cls, event_type: str = None) -> List[Dict]:
        """Get logged events, optionally filtered by type."""
        if event_type:
            return [e for e in cls._event_log if e["event"] == event_type]
        return cls._event_log.copy()

    @classmethod
    def clear(cls):
        """Clear event log and subscribers."""
        cls._event_log = []
        cls._subscribers = []


# Standard event types
class Events:
    """Standard event type constants."""

    STATE_CHANGE = "STATE_CHANGE"
    AGENT_START = "AGENT_START"
    AGENT_COMPLETE = "AGENT_COMPLETE"
    AGENT_ERROR = "AGENT_ERROR"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REFLEXION_TRIGGERED = "REFLEXION_TRIGGERED"
    WORKFLOW_COMPLETE = "WORKFLOW_COMPLETE"


class JSONFormatter(logging.Formatter):
    """
    JSON structured logging formatter for complete traceability.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": record.name,
            "level": record.levelname,
            "action": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
        }

        # Add extra fields if present
        if hasattr(record, "stage"):
            log_entry["stage"] = record.stage
        if hasattr(record, "faq_count"):
            log_entry["faq_count"] = record.faq_count

        return json.dumps(log_entry)


def setup_json_logging(log_file: str = "output/trace.log"):
    """
    Configure JSON structured logging.
    """
    import os

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # File handler with JSON format
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.INFO)

    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    logger.info("JSON logging initialized", extra={"trace_id": "system"})
