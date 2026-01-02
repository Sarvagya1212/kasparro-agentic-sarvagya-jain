import sys
import unittest

# Ensure project root is in path
sys.path.append(".")


class TestAgentImplementations(unittest.TestCase):
    def test_import(self):
        """Verify that agent_implementations.py can be imported and expected agents exist."""
        try:
            from skincare_agent_system.actors import agent_implementations

            # Check for existing agents
            self.assertTrue(hasattr(agent_implementations, "DataAgent"))
            self.assertTrue(hasattr(agent_implementations, "SyntheticDataAgent"))
            self.assertTrue(hasattr(agent_implementations, "GenerationAgent"))

            # Check for removed agents (should NOT exist)
            self.assertFalse(hasattr(agent_implementations, "AnalysisAgent"))
            self.assertFalse(hasattr(agent_implementations, "ValidationAgent"))

            print(
                "Import check passed: Existing agents found, obsolete agents removed."
            )
        except ImportError as e:
            self.fail(f"Failed to import agent_implementations: {e}")
        except Exception as e:
            self.fail(f"Unexpected error: {e}")


if __name__ == "__main__":
    unittest.main()
