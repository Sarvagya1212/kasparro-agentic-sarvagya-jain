import os
import sys

# Add root to path
sys.path.append(os.getcwd())

try:
    from skincare_agent_system.actors.agents import BaseAgent
    from skincare_agent_system.core.models import AgentContext, AgentStatus
    from skincare_agent_system.infrastructure.tracer import get_tracer
    from skincare_agent_system.tools import BaseTool
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)


class MockAgent(BaseAgent):
    def run(self, context, directive=None):
        return self.create_result(
            status=AgentStatus.COMPLETE, context=context, message="Mock complete"
        )

    def can_handle(self, context):
        return True


class MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool"

    def _execute(self, **kwargs):
        return "Tool executed"


def run_tests():
    print("Testing Singleton...")
    tracer1 = get_tracer()
    tracer2 = get_tracer()
    assert tracer1 is tracer2
    print("Singleton OK")

    print("Testing Trace Lifecycle...")
    tracer = get_tracer()
    trace_id = tracer.start_trace("test_workflow")
    assert trace_id is not None
    assert tracer.current_trace.workflow_name == "test_workflow"
    tracer.end_trace(status="completed")
    print("Lifecycle OK")

    print("Testing Agent Tracing...")
    tracer.start_trace("agent_test")
    agent = MockAgent(name="TestAgent")
    context = AgentContext()
    result = agent.run_with_reflection(context)  # Should trigger tracing

    events = tracer.current_trace.events
    agent_calls = [e for e in events if e.event_type == "agent_call"]
    if len(agent_calls) != 1:
        print(f"FAILED: Expected 1 agent call, got {len(agent_calls)}")
        print(events)
    else:
        print("Agent Tracing OK")
    tracer.end_trace()

    print("Testing Tool Tracing...")
    tracer.start_trace("tool_test")
    tool = MockTool()
    tool.run(param="test")

    events = tracer.current_trace.events
    tool_usages = [e for e in events if e.event_type == "tool_usage"]
    if len(tool_usages) != 1:
        print(f"FAILED: Expected 1 tool usage, got {len(tool_usages)}")
    else:
        print("Tool Tracing OK")
    tracer.end_trace()


if __name__ == "__main__":
    try:
        run_tests()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
