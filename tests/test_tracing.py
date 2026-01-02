from unittest.mock import MagicMock, patch

import pytest

from skincare_agent_system.actors.agents import BaseAgent
from skincare_agent_system.core.orchestrator import Orchestrator
from skincare_agent_system.infrastructure.tracer import ExecutionTracer, get_tracer
from skincare_agent_system.tools import BaseTool


class MockAgent(BaseAgent):
    def run(self, context, directive=None):
        return self.create_result(
            status="COMPLETE", context=context, message="Mock complete"
        )

    def can_handle(self, context):
        return True


class MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool"

    def _execute(self, **kwargs):
        return "Tool executed"


def test_singleton_tracer():
    tracer1 = get_tracer()
    tracer2 = get_tracer()
    assert tracer1 is tracer2


def test_trace_lifecycle():
    tracer = get_tracer()
    trace_id = tracer.start_trace("test_workflow")
    assert trace_id is not None
    assert tracer.current_trace.workflow_name == "test_workflow"
    assert tracer.current_trace.status == "running"

    tracer.end_trace(status="completed")
    assert tracer.current_trace.status == "completed"
    assert tracer.current_trace.end_time is not None


def test_agent_tracing():
    tracer = get_tracer()
    tracer.start_trace("agent_test")

    agent = MockAgent(name="TestAgent")
    # Mocking run needed because direct call bypasses orchestrator setup but BaseAgent.run_with_reflection calls run
    # Actually BaseAgent.run_with_reflection is what we call to trigger tracing if we called it directly.
    # But usually Orchestrator calls run(). Wait, my modification was in BaseAgent.run_with_reflection.
    # Let's verify where I put the tracing code in agents.py.
    # I put it in run_with_reflection.

    from skincare_agent_system.core.models import AgentContext

    context = AgentContext()

    # We need to call run_with_reflection to trigger the tracing wrapper
    # But BaseAgent.run_with_reflection calls self.run

    # Let's mock the run method to avoid errors? No, MockAgent implements run.

    result = agent.run_with_reflection(context)

    events = tracer.current_trace.events
    agent_calls = [e for e in events if e.event_type == "agent_call"]
    assert len(agent_calls) == 1
    assert agent_calls[0].name == "TestAgent"
    assert agent_calls[0].metadata["status"] == "COMPLETE"

    tracer.end_trace()


def test_tool_tracing():
    tracer = get_tracer()
    tracer.start_trace("tool_test")

    tool = MockTool()
    tool.run(param="test")

    events = tracer.current_trace.events
    tool_usages = [e for e in events if e.event_type == "tool_usage"]
    assert len(tool_usages) == 1
    assert tool_usages[0].name == "mock_tool"
    assert tool_usages[0].input_data["param"] == "test"

    tracer.end_trace()
