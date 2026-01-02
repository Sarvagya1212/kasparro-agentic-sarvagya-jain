import unittest
from unittest.mock import MagicMock, patch

from skincare_agent_system.evaluation import FailureAnalyzer, LLMJudge
from skincare_agent_system.evaluation_dataset import GoldenDataset
from skincare_agent_system.evaluation_dataset import TestCase as EvalTestCase
from skincare_agent_system.infrastructure.llm_client import LLMClient


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=LLMClient)
        self.mock_client.is_available.return_value = True
        self.mock_client.generate_json.return_value = {
            "score": 0.9,
            "reason": "Good execution",
            "failures": [],
        }

    @patch("skincare_agent_system.evaluation.get_llm_client")
    def test_llm_judge(self, mock_get_client):
        mock_get_client.return_value = self.mock_client

        judge = LLMJudge()
        test_case = EvalTestCase(
            id="TC-001",
            input_data={"product": "Serum"},
            expected_output={"status": "complete"},
            criteria=["no_errors"],
        )
        trace_summary = {"status": "completed", "total_events": 5, "errors": 0}

        result = judge.evaluate_trace(trace_summary, test_case)
        self.assertEqual(result["score"], 0.9)
        self.assertEqual(result["reason"], "Good execution")

        # Verify prompt construction (partially)
        self.mock_client.generate_json.assert_called_once()
        args = self.mock_client.generate_json.call_args
        prompt = args[0][0]
        self.assertIn("TC-001", prompt)
        self.assertIn("no_errors", prompt)

    def test_dataset_lifecycle(self):
        dataset = GoldenDataset("tests/temp_dataset.json")
        tc = EvalTestCase(id="TC-TEST", input_data={}, expected_output={}, criteria=[])
        dataset.add_case(tc)

        dataset.save()

        # Reload
        new_dataset = GoldenDataset("tests/temp_dataset.json")
        new_dataset.load()
        self.assertEqual(len(new_dataset.test_cases), 1)
        self.assertEqual(new_dataset.test_cases[0].id, "TC-TEST")

        # Cleanup
        import os

        if os.path.exists("tests/temp_dataset.json"):
            os.remove("tests/temp_dataset.json")


if __name__ == "__main__":
    unittest.main()
