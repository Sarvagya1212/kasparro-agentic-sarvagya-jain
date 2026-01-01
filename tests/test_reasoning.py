"""
Tests for Reasoning and Reflection (Core Pillars of Autonomy).
Run with: pytest tests/test_reasoning.py -v
"""

import pytest

from skincare_agent_system.models import AgentContext, ProductData, AnalysisResults
from skincare_agent_system.reasoning import (
    ChainOfThought,
    ReActReasoner,
    ReasoningChain,
    TaskDecomposer,
    ThoughtStep,
    ThoughtType,
)
from skincare_agent_system.reflection import (
    ReflectionResult,
    SelfReflector,
)
from skincare_agent_system.memory import SessionState


class TestThoughtStep:
    """Tests for ThoughtStep."""

    def test_thought_creation(self):
        """Should create thought step."""
        step = ThoughtStep(
            type=ThoughtType.REASONING,
            content="Testing reasoning",
            confidence=0.9
        )
        assert step.type == ThoughtType.REASONING
        assert step.confidence == 0.9

    def test_thought_repr(self):
        """Should have readable repr."""
        step = ThoughtStep(
            type=ThoughtType.DECISION,
            content="Decide to proceed",
            confidence=1.0
        )
        assert "[DECISION]" in repr(step)


class TestReasoningChain:
    """Tests for ReasoningChain."""

    def test_add_thoughts(self):
        """Should add thoughts to chain."""
        chain = ReasoningChain(goal="Test goal")
        chain.observe("Saw something")
        chain.reason("Because of X")
        chain.decide("Do Y")

        assert len(chain.steps) == 3
        assert chain.final_decision == "Do Y"

    def test_to_log(self):
        """Should convert to log format."""
        chain = ReasoningChain(goal="Test")
        chain.observe("Observation 1")
        chain.act("Action 1")

        log = chain.to_log()
        assert len(log) == 2
        assert "[OBSERVATION]" in log[0]


class TestReActReasoner:
    """Tests for ReActReasoner."""

    def test_start_chain(self):
        """Should start reasoning chain."""
        reasoner = ReActReasoner()
        chain = reasoner.start_chain("Generate content")

        assert chain.goal == "Generate content"
        assert len(reasoner.chains) == 1

    def test_reason_about_empty_context(self):
        """Should reason about empty context."""
        reasoner = ReActReasoner()
        context = AgentContext()
        chain = reasoner.start_chain("Process data")

        reasoner.reason_about_context(chain, context)

        # Should observe no data
        assert any("no product data" in s.content.lower() for s in chain.steps)
        # Should decide to use DataAgent
        assert chain.final_decision is not None
        assert "DataAgent" in chain.final_decision

    def test_reason_about_complete_context(self):
        """Should reason about complete context."""
        reasoner = ReActReasoner()
        context = AgentContext()
        context.product_data = ProductData(
            name="Test", brand="TestBrand", key_ingredients=["A"]
        )
        context.comparison_data = ProductData(
            name="Comp", brand="CompBrand", key_ingredients=["B"]
        )
        context.analysis_results = AnalysisResults(benefits=["b1"], usage="u")
        context.is_valid = True

        chain = reasoner.start_chain("Check context")
        reasoner.reason_about_context(chain, context)

        # Should observe validated
        assert any("validated" in s.content.lower() for s in chain.steps)
        assert "GenerationAgent" in chain.final_decision


class TestTaskDecomposer:
    """Tests for HTN-style task decomposition."""

    def test_decompose_content_goal(self):
        """Should decompose content generation goal."""
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose_goal("Generate content pages")

        assert len(tasks) >= 5
        assert tasks[0].description == "Load product data"
        assert tasks[0].assigned_agent == "DataAgent"

    def test_get_next_executable(self):
        """Should get next executable task."""
        decomposer = TaskDecomposer()
        decomposer.decompose_goal("Generate content")

        next_task = decomposer.get_next_executable()
        assert next_task is not None
        assert next_task.id == "t1"

    def test_mark_complete_and_progress(self):
        """Should progress after marking complete."""
        decomposer = TaskDecomposer()
        decomposer.decompose_goal("Generate content")

        # Mark first task complete
        decomposer.mark_complete("t1")

        # Next executable should be t2
        next_task = decomposer.get_next_executable()
        assert next_task.id == "t2"


class TestChainOfThought:
    """Tests for CoT helper."""

    def test_generate_reasoning_no_data(self):
        """Should generate reasoning for empty context."""
        context = AgentContext()
        thoughts = ChainOfThought.generate_reasoning("Agent", context, "load data")

        assert len(thoughts) >= 2
        assert any("no product data" in t.lower() for t in thoughts)

    def test_generate_reasoning_with_data(self):
        """Should generate reasoning for context with data."""
        context = AgentContext()
        context.product_data = ProductData(
            name="GlowBoost", brand="Brand", key_ingredients=["VitC"]
        )
        context.is_valid = True

        thoughts = ChainOfThought.generate_reasoning("Agent", context, "generate")

        assert any("GlowBoost" in t for t in thoughts)
        assert any("validated" in t.lower() for t in thoughts)


class TestSelfReflector:
    """Tests for SelfReflector."""

    def test_reflect_on_data_agent(self):
        """Should reflect on DataAgent output."""
        reflector = SelfReflector()
        context = AgentContext()
        context.product_data = ProductData(
            name="Test", brand="Brand", key_ingredients=["A", "B"], price=100
        )

        result = reflector.reflect_on_output("DataAgent", None, context)

        assert result.is_acceptable is True
        assert result.confidence > 0

    def test_reflect_critical_issue(self):
        """Should detect critical issues."""
        reflector = SelfReflector()
        context = AgentContext()
        # No product data

        result = reflector.reflect_on_output("DataAgent", None, context)

        assert result.has_critical_issues() is True

    def test_reflection_log(self):
        """Should maintain reflection log."""
        reflector = SelfReflector()
        context = AgentContext()

        reflector.reflect_on_output("TestAgent", None, context)
        reflector.reflect_on_output("TestAgent2", None, context)

        log = reflector.get_reflection_log()
        assert len(log) == 2


class TestSessionState:
    """Tests for SessionState."""

    def test_preferences(self):
        """Should store and retrieve preferences."""
        session = SessionState(session_id="test123")
        session.set_preference("theme", "dark")

        assert session.get_preference("theme") == "dark"
        assert session.get_preference("missing", "default") == "default"

    def test_interaction_history(self):
        """Should track interaction history."""
        session = SessionState()
        session.add_interaction({"action": "load", "agent": "DataAgent"})
        session.add_interaction({"action": "analyze", "agent": "AnalysisAgent"})

        assert len(session.interaction_history) == 2
        assert session.interaction_history[0]["action"] == "load"

    def test_learned_patterns(self):
        """Should learn patterns."""
        session = SessionState()
        session.learn_pattern("User prefers vitamin C products")
        session.learn_pattern("User prefers vitamin C products")  # Duplicate

        assert len(session.learned_patterns) == 1

    def test_variables(self):
        """Should store context variables."""
        session = SessionState()
        session.set_variable("last_product", "GlowBoost")

        assert session.get_variable("last_product") == "GlowBoost"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
