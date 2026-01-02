import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in path
sys.path.append(".")

from skincare_agent_system.actors.delegator import DelegatorAgent
from skincare_agent_system.core.models import AgentContext, ProductData
from skincare_agent_system.security.credential_shim import get_credential_shim


class TestDelegatorIdentity(unittest.TestCase):
    def test_delegator_pass_identity(self):
        """Verify DelegatorAgent passes correct identity to LLMClient."""

        # Mock LLM Client
        mock_llm = MagicMock()
        mock_llm.generate_json.return_value = {
            "should_delegate": True,
            "confidence": 0.9,
            "reasoning": "Test reasoning",
        }

        # Mock Shim to allow "agent_DelegatorAgent"
        mock_shim = MagicMock()
        mock_shim.get_credential_for_agent.return_value = "fake_key"

        with patch(
            "skincare_agent_system.actors.delegator.DelegatorAgent._get_llm",
            return_value=mock_llm,
        ), patch(
            "skincare_agent_system.security.credential_shim.get_credential_shim",
            return_value=mock_shim,
        ):

            agent = DelegatorAgent()

            # Setup context
            context = AgentContext()
            context.product_data = ProductData(
                name="Test",
                brand="Brand",
                price=10,
                currency="USD",
                key_ingredients=[],
                benefits=[],
            )
            context.comparison_data = ProductData(
                name="Comp",
                brand="Brand",
                price=10,
                currency="USD",
                key_ingredients=[],
                benefits=[],
            )

            # Run propose
            proposal = agent.propose(context)

            # Verify generate_json was called with correct identity
            mock_llm.generate_json.assert_called_once()
            call_kwargs = mock_llm.generate_json.call_args[1]
            self.assertEqual(call_kwargs.get("agent_identity"), "agent_DelegatorAgent")
            print("Verified: DelegatorAgent passed 'agent_DelegatorAgent' identity.")


if __name__ == "__main__":
    unittest.main()
