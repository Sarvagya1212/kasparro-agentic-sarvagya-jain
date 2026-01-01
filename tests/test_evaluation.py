"""
Tests for Evaluation and Observability features.
Run with: pytest tests/test_evaluation.py
"""

import pytest

from skincare_agent_system.evaluation import (
    FailureAnalyzer,
    FailureCategory,
)
from skincare_agent_system.tracer import ExecutionTracer


class TestFailureAnalyzer:
    """Tests for failure analysis."""

    def test_categorize_safety_violation(self):
        """Should categorize safety violations."""
        analyzer = FailureAnalyzer()
        category = analyzer.categorize_failure(
            "Input blocked by guardrails",
            "Coordinator"
        )
        assert category == FailureCategory.SAFETY_VIOLATION

    def test_categorize_validation_error(self):
        """Should categorize validation errors."""
        analyzer = FailureAnalyzer()
        category = analyzer.categorize_failure(
            "Missing required field: name",
            "ValidationAgent"
        )
        assert category == FailureCategory.VALIDATION_ERROR

    def test_categorize_tool_failure(self):
        """Should categorize tool failures."""
        analyzer = FailureAnalyzer()
        category = analyzer.categorize_failure(
            "Tool not found: benefits_extractor",
            "BenefitsWorker"
        )
        assert category == FailureCategory.TOOL_FAILURE

    def test_failure_report(self):
        """Should generate failure report."""
        analyzer = FailureAnalyzer()
        analyzer.categorize_failure("blocked input", "Agent1")
        analyzer.categorize_failure("validation failed", "Agent2")
        analyzer.categorize_failure("tool error", "Agent1")

        report = analyzer.get_failure_report()

        assert report["total"] == 3
        assert "by_category" in report
        assert "by_agent" in report

    def test_improvement_suggestions(self):
        """Should generate improvement suggestions."""
        analyzer = FailureAnalyzer()
        analyzer.categorize_failure("blocked by safety", "Agent")

        suggestions = analyzer.get_improvement_suggestions()

        assert len(suggestions) > 0
        assert any("guardrails" in s.lower() for s in suggestions)


class TestExecutionTracer:
    """Tests for execution tracing."""

    def test_start_trace(self, tmp_path):
        """Should start a new trace."""
        tracer = ExecutionTracer(output_dir=str(tmp_path))
        trace_id = tracer.start_trace("test_workflow")

        assert trace_id is not None
        assert len(trace_id) == 8
        assert tracer.current_trace is not None

    def test_log_agent_call(self, tmp_path):
        """Should log agent calls."""
        tracer = ExecutionTracer(output_dir=str(tmp_path))
        tracer.start_trace()

        tracer.log_agent_call(
            agent="TestAgent",
            input_summary={"data": "test"},
            output_summary={"result": "ok"},
            duration_ms=50.5
        )

        assert len(tracer.current_trace.events) == 1
        assert tracer.current_trace.events[0].event_type == "agent_call"

    def test_log_tool_usage(self, tmp_path):
        """Should log tool usage."""
        tracer = ExecutionTracer(output_dir=str(tmp_path))
        tracer.start_trace()

        tracer.log_tool_usage(
            tool_name="benefits_extractor",
            args={"product_data": {}},
            result=["benefit1", "benefit2"],
            duration_ms=25.0
        )

        assert len(tracer.current_trace.events) == 1
        assert tracer.current_trace.events[0].event_type == "tool_usage"

    def test_end_trace(self, tmp_path):
        """Should end trace with summary."""
        tracer = ExecutionTracer(output_dir=str(tmp_path))
        tracer.start_trace()
        tracer.log_agent_call("Agent1", {}, {}, 10)
        tracer.log_agent_call("Agent2", {}, {}, 20)

        trace = tracer.end_trace("completed")

        assert trace.status == "completed"
        assert trace.total_duration_ms is not None
        assert trace.summary["agent_calls"] == 2

    def test_export_trace(self, tmp_path):
        """Should export trace to JSON."""
        tracer = ExecutionTracer(output_dir=str(tmp_path))
        tracer.start_trace()
        tracer.log_agent_call("TestAgent", {}, {}, 10)
        tracer.end_trace()

        filepath = tracer.export_trace()

        assert filepath.endswith(".json")
        import json
        with open(filepath) as f:
            data = json.load(f)
        assert data["trace_id"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
