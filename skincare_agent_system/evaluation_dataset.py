import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Dataset")


@dataclass
class TestCase:
    """A single test case in the Golden Dataset."""

    id: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    criteria: List[
        str
    ]  # Evaluation criteria (e.g., "no_hallucinations", "follows_schema")
    metadata: Dict[str, Any] = field(default_factory=dict)


class GoldenDataset:
    """
    Manages the Golden Dataset for evaluation.
    """

    def __init__(self, filepath: str = "data/golden_dataset.json"):
        self.filepath = Path(filepath)
        self.test_cases: List[TestCase] = []

    def load(self):
        """Load dataset from file."""
        if not self.filepath.exists():
            logger.warning(f"Dataset file not found: {self.filepath}")
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.test_cases = [
                    TestCase(**item) for item in data.get("test_cases", [])
                ]
            logger.info(
                f"Loaded {len(self.test_cases)} test cases from {self.filepath}"
            )
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")

    def save(self):
        """Save dataset to file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "test_cases": [
                {
                    "id": tc.id,
                    "input_data": tc.input_data,
                    "expected_output": tc.expected_output,
                    "criteria": tc.criteria,
                    "metadata": tc.metadata,
                }
                for tc in self.test_cases
            ]
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(self.test_cases)} test cases to {self.filepath}")

    def add_case(self, test_case: TestCase):
        """Add a new test case."""
        self.test_cases.append(test_case)

    def get_case(self, case_id: str) -> Optional[TestCase]:
        """Get a test case by ID."""
        for tc in self.test_cases:
            if tc.id == case_id:
                return tc
        return None
