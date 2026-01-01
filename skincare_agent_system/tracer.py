"""
Execution Tracer: Observability for agent execution.
Logs agent calls, tool usage, and exports traces for visualization.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Tracer")


@dataclass
class TraceEvent:
    """A single trace event."""
    event_type: str  # "agent_call", "tool_usage", "decision", "error"
    name: str
    timestamp: str
    duration_ms: Optional[float] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """Complete execution trace for a workflow."""
    trace_id: str
    workflow_name: str
    start_time: str
    end_time: Optional[str] = None
    events: List[TraceEvent] = field(default_factory=list)
    total_duration_ms: Optional[float] = None
    status: str = "running"  # running, completed, failed
    summary: Dict[str, Any] = field(default_factory=dict)


class ExecutionTracer:
    """
    Traces agent execution for observability.
    Logs calls, tool usage, and exports traces.
    """

    def __init__(self, output_dir: str = "traces"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_trace: Optional[ExecutionTrace] = None
        self._start_time: Optional[float] = None

    def start_trace(self, workflow_name: str = "content_generation") -> str:
        """
        Start a new execution trace.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Trace ID
        """
        trace_id = str(uuid.uuid4())[:8]
        self.current_trace = ExecutionTrace(
            trace_id=trace_id,
            workflow_name=workflow_name,
            start_time=datetime.now().isoformat()
        )
        self._start_time = time.time()
        logger.info(f"Trace started: {trace_id}")
        return trace_id

    def log_agent_call(
        self,
        agent: str,
        input_summary: Dict[str, Any],
        output_summary: Dict[str, Any],
        duration_ms: float,
        status: str = "success"
    ):
        """Log an agent execution."""
        if not self.current_trace:
            return

        event = TraceEvent(
            event_type="agent_call",
            name=agent,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            input_data=input_summary,
            output_data=output_summary,
            metadata={"status": status}
        )
        self.current_trace.events.append(event)
        logger.debug(f"Traced agent call: {agent} ({duration_ms:.2f}ms)")

    def log_tool_usage(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        duration_ms: float
    ):
        """Log tool usage."""
        if not self.current_trace:
            return

        # Truncate large data
        args_summary = {k: str(v)[:100] for k, v in args.items()}
        result_summary = str(result)[:200] if result else None

        event = TraceEvent(
            event_type="tool_usage",
            name=tool_name,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            input_data=args_summary,
            output_data={"result": result_summary}
        )
        self.current_trace.events.append(event)

    def log_decision(self, agent: str, decision: str, reason: str = ""):
        """Log a decision point."""
        if not self.current_trace:
            return

        event = TraceEvent(
            event_type="decision",
            name=agent,
            timestamp=datetime.now().isoformat(),
            metadata={"decision": decision, "reason": reason}
        )
        self.current_trace.events.append(event)

    def log_error(self, agent: str, error: str, category: str = "unknown"):
        """Log an error."""
        if not self.current_trace:
            return

        event = TraceEvent(
            event_type="error",
            name=agent,
            timestamp=datetime.now().isoformat(),
            metadata={"error": error, "category": category}
        )
        self.current_trace.events.append(event)

    def end_trace(self, status: str = "completed") -> Optional[ExecutionTrace]:
        """
        End the current trace.

        Args:
            status: Final status (completed, failed)

        Returns:
            The completed trace
        """
        if not self.current_trace:
            return None

        self.current_trace.end_time = datetime.now().isoformat()
        self.current_trace.status = status

        if self._start_time:
            self.current_trace.total_duration_ms = (
                (time.time() - self._start_time) * 1000
            )

        # Generate summary
        self.current_trace.summary = self._generate_summary()

        logger.info(
            f"Trace ended: {self.current_trace.trace_id} "
            f"({self.current_trace.total_duration_ms:.2f}ms)"
        )

        return self.current_trace

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate trace summary."""
        if not self.current_trace:
            return {}

        events = self.current_trace.events
        agent_calls = [e for e in events if e.event_type == "agent_call"]
        tool_usages = [e for e in events if e.event_type == "tool_usage"]
        errors = [e for e in events if e.event_type == "error"]

        return {
            "total_events": len(events),
            "agent_calls": len(agent_calls),
            "tool_usages": len(tool_usages),
            "errors": len(errors),
            "agents_involved": list(set(e.name for e in agent_calls)),
            "tools_used": list(set(e.name for e in tool_usages)),
        }

    def export_trace(self, filename: Optional[str] = None) -> str:
        """
        Export trace to JSON file.

        Args:
            filename: Optional filename (defaults to trace_id.json)

        Returns:
            Path to exported file
        """
        if not self.current_trace:
            raise ValueError("No trace to export")

        if not filename:
            filename = f"trace_{self.current_trace.trace_id}.json"

        filepath = self.output_dir / filename

        # Convert to dict
        trace_dict = {
            "trace_id": self.current_trace.trace_id,
            "workflow_name": self.current_trace.workflow_name,
            "start_time": self.current_trace.start_time,
            "end_time": self.current_trace.end_time,
            "total_duration_ms": self.current_trace.total_duration_ms,
            "status": self.current_trace.status,
            "summary": self.current_trace.summary,
            "events": [
                {
                    "event_type": e.event_type,
                    "name": e.name,
                    "timestamp": e.timestamp,
                    "duration_ms": e.duration_ms,
                    "input": e.input_data,
                    "output": e.output_data,
                    "metadata": e.metadata
                }
                for e in self.current_trace.events
            ]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(trace_dict, f, indent=2)

        logger.info(f"Trace exported to: {filepath}")
        return str(filepath)

    def get_trace_summary(self) -> Dict[str, Any]:
        """Get current trace summary."""
        if not self.current_trace:
            return {"status": "no_active_trace"}

        return {
            "trace_id": self.current_trace.trace_id,
            "status": self.current_trace.status,
            "events": len(self.current_trace.events),
            "summary": self.current_trace.summary
        }
