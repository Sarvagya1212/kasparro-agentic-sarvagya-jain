"""
Tests for Memory and State Management features.
Run with: pytest tests/test_memory.py
"""

import pytest

from skincare_agent_system.cognition.memory import (
    ContextCompressor,
    EpisodicMemory,
    KnowledgeBase,
    MemorySystem,
    WorkingMemory,
)
from skincare_agent_system.core.state_manager import (
    StateManager,
    StateSpace,
    WorkflowStatus,
)


class TestWorkingMemory:
    """Tests for short-term working memory."""

    def test_set_task(self):
        """Working memory should store current task."""
        wm = WorkingMemory()
        wm.set_task("analyze_product", {"product_id": "123"})

        assert wm.current_task == "analyze_product"
        assert wm.active_parameters["product_id"] == "123"

    def test_clear(self):
        """Clear should reset working memory."""
        wm = WorkingMemory()
        wm.set_task("test_task")
        wm.add_result({"data": "test"})

        wm.clear()

        assert wm.current_task is None
        assert wm.intermediate_results == []


class TestEpisodicMemory:
    """Tests for episodic memory."""

    def test_add_episode(self):
        """Should record episodes."""
        em = EpisodicMemory()
        em.add_episode(
            agent="TestAgent",
            action="test_action",
            outcome="success",
            context_summary="Test context",
        )

        assert len(em.episodes) == 1
        assert em.episodes[0].agent == "TestAgent"

    def test_get_similar_episodes(self):
        """Should filter episodes by agent/action."""
        em = EpisodicMemory()
        em.add_episode("AgentA", "action1", "success", "ctx1")
        em.add_episode("AgentB", "action2", "failure", "ctx2")
        em.add_episode("AgentA", "action3", "success", "ctx3")

        results = em.get_similar_episodes(agent="AgentA")

        assert len(results) == 2
        assert all(e.agent == "AgentA" for e in results)

    def test_success_rate(self):
        """Should calculate success rate."""
        em = EpisodicMemory()
        em.add_episode("Agent", "a", "success", "")
        em.add_episode("Agent", "b", "success", "")
        em.add_episode("Agent", "c", "failure", "")

        rate = em.get_success_rate("Agent")

        assert rate == pytest.approx(0.666, rel=0.01)


class TestContextCompressor:
    """Tests for context compression."""

    def test_no_compression_needed(self):
        """Should not compress short history."""
        history = [{"step": i} for i in range(5)]
        result = ContextCompressor.compress(history, max_items=10)

        assert result["type"] == "full"
        assert len(result["items"]) == 5

    def test_compression_applied(self):
        """Should compress long history."""
        history = [{"step": i, "agent": f"Agent{i % 3}"} for i in range(30)]
        result = ContextCompressor.compress(history, max_items=10)

        assert result["type"] == "compressed"
        assert len(result["recent_items"]) == 10
        assert result["summarized_count"] == 20
        assert "summary" in result


class TestStateSpace:
    """Tests for structured state space."""

    def test_transition(self):
        """Should record state transitions."""
        state = StateSpace()
        state.available_actions = ["load_data", "analyze"]

        result = state.transition("load_data", "DataAgent", {"status": "ok"})

        assert result is True
        assert state.current_agent == "DataAgent"
        assert len(state.transition_history) == 1

    def test_invalid_transition(self):
        """Should reject invalid transitions."""
        state = StateSpace()
        state.available_actions = ["load_data"]

        result = state.transition("invalid_action", "Agent")

        assert result is False

    def test_set_phase(self):
        """Should update phase and available actions."""
        state = StateSpace()
        state.set_phase("analysis", ["analyze", "validate"])

        assert state.current_phase == "analysis"
        assert "analyze" in state.available_actions


class TestStateManager:
    """Tests for state manager."""

    def test_checkpoint_rollback(self):
        """Should checkpoint and rollback state."""
        manager = StateManager()
        manager.start_workflow()
        manager.checkpoint()

        # Make changes
        manager.get_state().workflow_status = WorkflowStatus.ERROR

        # Rollback
        manager.rollback()

        assert manager.get_state().workflow_status == WorkflowStatus.PROCESSING


class TestMemorySystem:
    """Tests for unified memory system."""

    def test_start_session(self):
        """Should initialize working memory for session."""
        ms = MemorySystem(knowledge_base_path="data/test_kb.json")
        ms.start_session("test_task", {"param": "value"})

        assert ms.working.current_task == "test_task"

    def test_record_outcome(self):
        """Should record outcomes in episodic memory."""
        ms = MemorySystem(knowledge_base_path="data/test_kb.json")
        ms.record_outcome("Agent", "action", True, "context")

        assert len(ms.episodic.episodes) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
