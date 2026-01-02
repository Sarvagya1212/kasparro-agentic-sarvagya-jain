import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skincare_agent_system.actors.agent_implementations import (
    DataAgent,
    GenerationAgent,
)
from skincare_agent_system.actors.delegator import DelegatorAgent
from skincare_agent_system.actors.verifier import VerifierAgent
from skincare_agent_system.core.models import AgentContext, ProductData
from skincare_agent_system.core.proposals import (
    AgentProposal,
    GoalManager,
    ProposalSystem,
)


class TestProposals(unittest.TestCase):
    def setUp(self):
        self.context = AgentContext()
        self.proposal_system = ProposalSystem()

    def test_collect_proposals(self):
        # Setup context
        self.context.product_data = None  # Should trigger DataAgent

        agents = {
            "DataAgent": DataAgent(),
            "DelegatorAgent": DelegatorAgent(),
            "VerifierAgent": VerifierAgent(),
            "GenerationAgent": GenerationAgent(),
        }

        # Manually invoke propose (bypassing orchestrator logic for unit test)
        proposals = []
        for agent in agents.values():
            p = agent.propose(self.context)
            if p:
                proposals.append(p)

        # DataAgent should propose with high confidence
        data_proposal = next(
            (p for p in proposals if p.agent_name == "DataAgent"), None
        )
        self.assertIsNotNone(data_proposal)
        self.assertGreater(data_proposal.confidence, 0.5)

        # GenerationAgent should NOT propose (or low confidence)
        gen_proposal = next(
            (p for p in proposals if p.agent_name == "GenerationAgent"), None
        )
        if gen_proposal:
            self.assertEqual(gen_proposal.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
