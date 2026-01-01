"""
Tests for Agent Proposal System (True Agent Autonomy).
Run with: pytest tests/test_proposals.py -v
"""

import pytest

from skincare_agent_system.models import AgentContext
from skincare_agent_system.proposals import (
    AgentProposal,
    Event,
    EventBus,
    EventType,
    Goal,
    GoalManager,
    ProposalSystem,
)
from skincare_agent_system.agent_implementations import (
    DataAgent,
    SyntheticDataAgent,
    AnalysisAgent,
    ValidationAgent,
    GenerationAgent,
)


class TestAgentProposal:
    """Tests for AgentProposal dataclass."""

    def test_proposal_creation(self):
        """Proposal should store all fields."""
        proposal = AgentProposal(
            agent_name="TestAgent",
            action="test_action",
            confidence=0.85,
            reason="Testing",
            preconditions_met=True,
            priority=5
        )

        assert proposal.agent_name == "TestAgent"
        assert proposal.confidence == 0.85
        assert proposal.preconditions_met is True

    def test_proposal_repr(self):
        """Proposal repr should be readable."""
        proposal = AgentProposal(
            agent_name="TestAgent",
            action="test",
            confidence=0.9,
            reason="Test reason",
            preconditions_met=True
        )

        repr_str = repr(proposal)
        assert "TestAgent" in repr_str
        assert "0.90" in repr_str


class TestProposalSystem:
    """Tests for ProposalSystem."""

    def test_collect_proposals_from_agents(self):
        """Should collect proposals from registered agents."""
        system = ProposalSystem()
        context = AgentContext()

        # Register agents
        data_agent = DataAgent()
        system.register_agent("DataAgent", data_agent)

        # Collect proposals
        proposals = system.collect_proposals(context)

        # DataAgent should propose (no data loaded)
        assert len(proposals) >= 1
        data_proposal = next((p for p in proposals if p.agent_name == "DataAgent"), None)
        assert data_proposal is not None
        assert data_proposal.confidence > 0

    def test_select_best_proposal_by_confidence(self):
        """Should select highest confidence proposal."""
        system = ProposalSystem()

        proposals = [
            AgentProposal("Agent1", "a", 0.7, "Low", True),
            AgentProposal("Agent2", "b", 0.95, "High", True),
            AgentProposal("Agent3", "c", 0.8, "Medium", True),
        ]

        best = system.select_best_proposal(proposals, strategy="highest_confidence")

        assert best.agent_name == "Agent2"
        assert best.confidence == 0.95

    def test_select_best_proposal_by_priority(self):
        """Should select highest priority proposal."""
        system = ProposalSystem()

        proposals = [
            AgentProposal("Agent1", "a", 0.7, "Low", True, priority=5),
            AgentProposal("Agent2", "b", 0.95, "High", True, priority=1),
            AgentProposal("Agent3", "c", 0.8, "Medium", True, priority=10),
        ]

        best = system.select_best_proposal(proposals, strategy="highest_priority")

        assert best.agent_name == "Agent3"
        assert best.priority == 10

    def test_filters_out_unmet_preconditions(self):
        """Should filter proposals with unmet preconditions."""
        system = ProposalSystem()

        proposals = [
            AgentProposal("Agent1", "a", 0.95, "High but blocked", False),
            AgentProposal("Agent2", "b", 0.5, "Low but ready", True),
        ]

        best = system.select_best_proposal(proposals)

        assert best.agent_name == "Agent2"


class TestAgentCanHandle:
    """Tests for agent can_handle() method."""

    def test_data_agent_can_handle_empty_context(self):
        """DataAgent should propose when no data."""
        agent = DataAgent()
        context = AgentContext()

        assert agent.can_handle(context) is True

    def test_data_agent_cannot_handle_with_data(self):
        """DataAgent should not propose when data exists."""
        from skincare_agent_system.models import ProductData

        agent = DataAgent()
        context = AgentContext()
        context.product_data = ProductData(
            name="Test", brand="TestBrand", key_ingredients=["A"], price=100
        )

        assert agent.can_handle(context) is False

    def test_analysis_agent_can_handle_with_data(self):
        """AnalysisAgent should propose when data exists but no analysis."""
        from skincare_agent_system.models import ProductData

        agent = AnalysisAgent()
        context = AgentContext()
        context.product_data = ProductData(
            name="Test", brand="TestBrand", key_ingredients=["A"], price=100
        )

        assert agent.can_handle(context) is True

    def test_generation_agent_needs_validation(self):
        """GenerationAgent should not propose without validation."""
        agent = GenerationAgent()
        context = AgentContext()
        context.is_valid = False

        assert agent.can_handle(context) is False


class TestAgentPropose:
    """Tests for agent propose() method."""

    def test_data_agent_proposes_with_high_confidence(self):
        """DataAgent should propose with high confidence when no data."""
        agent = DataAgent()
        context = AgentContext()

        proposal = agent.propose(context)

        assert proposal is not None
        assert proposal.confidence >= 0.9
        assert proposal.preconditions_met is True
        assert "load" in proposal.reason.lower() or "data" in proposal.reason.lower()

    def test_data_agent_low_confidence_when_data_exists(self):
        """DataAgent proposal should have low confidence when data exists."""
        from skincare_agent_system.models import ProductData

        agent = DataAgent()
        context = AgentContext()
        context.product_data = ProductData(
            name="Test", brand="TestBrand", key_ingredients=["A"], price=100
        )

        proposal = agent.propose(context)

        assert proposal.confidence == 0.0
        assert proposal.preconditions_met is False


class TestEventBus:
    """Tests for EventBus."""

    def test_publish_and_subscribe(self):
        """Should deliver events to subscribers."""
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("test_event", handler)
        bus.publish(Event(type="test_event", source="Test", payload={"data": 123}))

        assert len(received) == 1
        assert received[0].payload["data"] == 123

    def test_event_log(self):
        """Should maintain event log."""
        bus = EventBus()
        bus.publish(Event(type="event1", source="A"))
        bus.publish(Event(type="event2", source="B"))

        log = bus.get_event_log()
        assert len(log) == 2


class TestGoalManager:
    """Tests for GoalManager."""

    def test_add_and_get_pending_goals(self):
        """Should track pending goals."""
        manager = GoalManager()

        manager.add_goal(Goal(id="g1", description="Load data", success_criteria=[], priority=1))
        manager.add_goal(Goal(id="g2", description="Generate", success_criteria=[], priority=2))

        pending = manager.get_pending_goals()
        assert len(pending) == 2

    def test_mark_goal_achieved(self):
        """Should mark goals as achieved."""
        manager = GoalManager()
        manager.add_goal(Goal(id="g1", description="Test", success_criteria=[], priority=1))

        manager.mark_achieved("g1")

        pending = manager.get_pending_goals()
        assert len(pending) == 0

    def test_highest_priority_goal(self):
        """Should return highest priority goal."""
        manager = GoalManager()
        manager.add_goal(Goal(id="g1", description="Low", success_criteria=[], priority=1))
        manager.add_goal(Goal(id="g2", description="High", success_criteria=[], priority=10))

        highest = manager.get_highest_priority_goal()
        assert highest.id == "g2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
