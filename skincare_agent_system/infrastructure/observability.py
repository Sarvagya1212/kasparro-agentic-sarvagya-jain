"""
Observability: Distributed tracing and performance monitoring.
Uses OpenTelemetry-compatible interfaces for production deployment.
"""

import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

logger = logging.getLogger("Observability")


class SpanStatus(Enum):
    """Status of a trace span."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class SpanEvent:
    """Event within a span."""

    name: str
    timestamp: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """A single trace span."""

    span_id: str
    trace_id: str
    name: str
    parent_span_id: Optional[str] = None
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    duration_ms: float = 0.0

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an event to the span."""
        self.events.append(
            SpanEvent(
                name=name,
                timestamp=datetime.now().isoformat(),
                attributes=attributes or {},
            )
        )

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def end(self, status: SpanStatus = SpanStatus.OK) -> None:
        """End the span."""
        self.end_time = datetime.now().isoformat()
        self.status = status

        # Calculate duration
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        self.duration_ms = (end - start).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [
                {"name": e.name, "timestamp": e.timestamp, "attributes": e.attributes}
                for e in self.events
            ],
        }


@dataclass
class Trace:
    """A complete trace with multiple spans."""

    trace_id: str
    root_span: Optional[Span] = None
    spans: List[Span] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_span(self, span: Span) -> None:
        """Add a span to the trace."""
        self.spans.append(span)
        if span.parent_span_id is None:
            self.root_span = span

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get a span by ID."""
        for span in self.spans:
            if span.span_id == span_id:
                return span
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "spans": [s.to_dict() for s in self.spans],
            "total_duration_ms": sum(s.duration_ms for s in self.spans),
            "span_count": len(self.spans),
        }


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    timestamp: str
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


class MetricsCollector:
    """Collects and aggregates metrics."""

    def __init__(self, max_points: int = 10000):
        self._points: List[MetricPoint] = []
        self._max_points = max_points
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

    def increment(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        self._record(name, self._counters[key], labels)

    def gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        self._record(name, value, labels)

    def histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a histogram value."""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._record(name, value, labels)

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _record(
        self, name: str, value: float, labels: Optional[Dict[str, str]]
    ) -> None:
        """Record a metric point."""
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.now().isoformat(),
            labels=labels or {},
        )
        self._points.append(point)

        if len(self._points) > self._max_points:
            self._points = self._points[-self._max_points :]

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        return self._counters.get(self._make_key(name, labels), 0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value."""
        return self._gauges.get(self._make_key(name, labels), 0)

    def get_histogram_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
            }

        sorted_vals = sorted(values)
        count = len(sorted_vals)
        return {
            "count": count,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / count,
            "p50": sorted_vals[int(count * 0.5)],
            "p95": sorted_vals[int(count * 0.95)] if count > 20 else sorted_vals[-1],
            "p99": sorted_vals[int(count * 0.99)] if count > 100 else sorted_vals[-1],
        }


class Tracer:
    """
    Distributed tracing system.
    Compatible with OpenTelemetry concepts.
    """

    def __init__(self, service_name: str = "skincare_agent_system"):
        self._service_name = service_name
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}  # thread-local in production
        self._current_trace_id: Optional[str] = None
        self._metrics = MetricsCollector()
        self._max_traces = 100

    def start_trace(self, name: str = "workflow") -> Trace:
        """Start a new trace."""
        trace_id = str(uuid.uuid4())[:16]

        trace = Trace(trace_id=trace_id)
        self._traces[trace_id] = trace
        self._current_trace_id = trace_id

        # Start root span
        self.start_span(name)

        # Prune old traces
        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.keys())[0]
            del self._traces[oldest]

        return trace

    def start_span(
        self,
        name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span in current trace."""
        if not self._current_trace_id:
            self.start_trace()

        span_id = str(uuid.uuid4())[:16]

        # Use current active span as parent if not specified
        if parent_span_id is None and self._active_spans:
            parent_span_id = list(self._active_spans.values())[-1].span_id

        span = Span(
            span_id=span_id,
            trace_id=self._current_trace_id,
            name=name,
            parent_span_id=parent_span_id,
            attributes=attributes or {"service": self._service_name},
        )

        self._active_spans[span_id] = span
        self._traces[self._current_trace_id].add_span(span)

        return span

    def end_span(self, span_id: str, status: SpanStatus = SpanStatus.OK) -> None:
        """End a span."""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end(status)

            # Record duration metric
            self._metrics.histogram(
                "span_duration_ms", span.duration_ms, {"name": span.name}
            )

    @contextmanager
    def span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Generator[Span, None, None]:
        """Context manager for spans."""
        span = self.start_span(name, attributes=attributes)
        try:
            yield span
            self.end_span(span.span_id, SpanStatus.OK)
        except Exception as e:
            span.add_event("error", {"message": str(e)})
            self.end_span(span.span_id, SpanStatus.ERROR)
            raise

    def trace_function(self, name: Optional[str] = None) -> Callable:
        """Decorator to trace a function."""

        def decorator(func: Callable) -> Callable:
            span_name = name or func.__name__

            def wrapper(*args, **kwargs):
                with self.span(span_name) as span:
                    span.set_attribute("function", func.__name__)
                    result = func(*args, **kwargs)
                    return result

            async def async_wrapper(*args, **kwargs):
                with self.span(span_name) as span:
                    span.set_attribute("function", func.__name__)
                    result = await func(*args, **kwargs)
                    return result

            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper

        return decorator

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def get_current_trace(self) -> Optional[Trace]:
        """Get the current active trace."""
        if self._current_trace_id:
            return self._traces.get(self._current_trace_id)
        return None

    def record_agent_execution(
        self, agent_name: str, duration_ms: float, success: bool
    ) -> None:
        """Record agent execution metrics."""
        self._metrics.increment(
            "agent_executions_total",
            labels={"agent": agent_name, "success": str(success).lower()},
        )
        self._metrics.histogram(
            "agent_execution_duration_ms", duration_ms, {"agent": agent_name}
        )

    def get_metrics(self) -> MetricsCollector:
        """Get the metrics collector."""
        return self._metrics

    def export_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Export recent traces as dictionaries."""
        traces = list(self._traces.values())[-limit:]
        return [t.to_dict() for t in traces]


class AnomalyDetector:
    """Simple anomaly detection for agent behavior."""

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._latency_history: Dict[str, List[float]] = {}
        self._error_history: Dict[str, List[bool]] = {}
        self._thresholds: Dict[str, float] = {}

    def record_latency(
        self,
        agent_name: str,
        latency_ms: float,
    ) -> Optional[str]:
        """Record latency and detect anomalies."""
        if agent_name not in self._latency_history:
            self._latency_history[agent_name] = []

        history = self._latency_history[agent_name]
        history.append(latency_ms)

        if len(history) > self._window_size:
            history.pop(0)

        # Detect anomaly if > 3 standard deviations
        if len(history) >= 10:
            avg = sum(history) / len(history)
            std = (sum((x - avg) ** 2 for x in history) / len(history)) ** 0.5

            if std > 0 and latency_ms > avg + 3 * std:
                return f"High latency: {latency_ms:.1f}ms (avg: {avg:.1f}ms)"

        return None

    def record_error(self, agent_name: str, is_error: bool) -> Optional[str]:
        """Record error and detect high error rate."""
        if agent_name not in self._error_history:
            self._error_history[agent_name] = []

        history = self._error_history[agent_name]
        history.append(is_error)

        if len(history) > self._window_size:
            history.pop(0)

        # Alert if error rate > 20% in window
        if len(history) >= 10:
            error_rate = sum(history) / len(history)
            if error_rate > 0.2:
                return f"High error rate: {error_rate:.1%}"

        return None


# Singleton instances
_tracer: Optional[Tracer] = None
_anomaly_detector: Optional[AnomalyDetector] = None


def get_tracer() -> Tracer:
    """Get or create tracer singleton."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create anomaly detector singleton."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector


def reset_observability() -> None:
    """Reset observability (for testing)."""
    global _tracer, _anomaly_detector
    _tracer = None
    _anomaly_detector = None
