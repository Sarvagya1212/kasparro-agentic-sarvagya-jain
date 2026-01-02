import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(".")

from skincare_agent_system.tools.content_tools import FAQGeneratorTool


class TestToolIdentity(unittest.TestCase):
    def test_faq_tool_identity_pass(self):
        """Verify FAQGeneratorTool uses passed agent_identity."""

        # Mock LLM Client
        mock_llm = MagicMock()
        mock_llm.generate_json.return_value = [{"question": "Q?", "answer": "A"}]

        # Mock Shim
        mock_shim = MagicMock()
        mock_shim.get_credential_for_agent.return_value = "fake_key"

        with patch(
            "skincare_agent_system.infrastructure.llm_client.LLMClient",
            return_value=mock_llm,
        ), patch(
            "skincare_agent_system.security.credential_shim.get_credential_shim",
            return_value=mock_shim,
        ), patch.dict(
            os.environ, {"MISTRAL_API_KEY": "yes"}
        ):

            # Ensure env var is seen (patch.dict handles it)

            tool = FAQGeneratorTool()

            # Execute with specific identity
            tool._execute(
                product_data={"name": "Test"},
                min_questions=1,
                agent_identity="agent_TestWorker",
            )

            # Verify usage
            mock_llm.generate_json.assert_called_once()
            call_kwargs = mock_llm.generate_json.call_args[1]
            self.assertEqual(call_kwargs.get("agent_identity"), "agent_TestWorker")
            print("Verified: FAQGeneratorTool used 'agent_TestWorker' identity.")

    def test_generic_tool_args(self):
        """Verify other tools accept **kwargs without error."""
        from skincare_agent_system.tools.content_tools import BenefitsExtractorTool

        tool = BenefitsExtractorTool()
        try:
            # Should not raise TypeError
            tool._execute(
                product_data={"benefits": []},
                agent_identity="agent_TestWorker",
                extra_arg="testing",
            )
            print("Verified: BenefitsExtractorTool accepted extra kwargs.")
        except TypeError as e:
            self.fail(f"BenefitsExtractorTool raised TypeError with extra args: {e}")


if __name__ == "__main__":
    unittest.main()
