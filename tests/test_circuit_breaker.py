import unittest

from skincare_agent_system.security.hitl import CircuitBreaker


class TestCircuitBreaker(unittest.TestCase):
    def test_error_threshold(self):
        cb = CircuitBreaker(error_threshold=3)
        cb.record_error("agent_1")
        cb.record_error("agent_1")
        self.assertFalse(cb.is_tripped())

        cb.record_error("agent_1")
        self.assertTrue(cb.is_tripped())
        self.assertIn("Error threshold exceeded", cb.trip_reason)

    def test_loop_detection(self):
        cb = CircuitBreaker(loop_threshold=3)
        cb.record_action("agent_2", "run_tool")
        cb.record_action("agent_2", "run_tool")
        self.assertFalse(cb.is_tripped())

        cb.record_action("agent_2", "run_tool")
        self.assertTrue(cb.is_tripped())
        self.assertIn("Loop detected", cb.trip_reason)

    def test_reset(self):
        cb = CircuitBreaker(error_threshold=2)
        cb.record_error("agent_3")
        cb.record_error("agent_3")
        self.assertTrue(cb.is_tripped())

        cb.reset()
        self.assertFalse(cb.is_tripped())
        self.assertEqual(cb.error_counts, {})


if __name__ == "__main__":
    unittest.main()
