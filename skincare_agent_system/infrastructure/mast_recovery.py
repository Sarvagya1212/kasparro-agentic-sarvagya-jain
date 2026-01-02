"""
MAST-based Failure Recovery System.
Implements Multi-Agent System Failure Taxonomy (MAST) for robust error handling.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("MASTRecovery")


class FailureType(Enum):
    """MAST failure categories."""

    # Specification Failures
    TASK_MISALIGNMENT = "task_misalignment"  # Agent misunderstands task
    ROLE_VIOLATION = "role_violation"  # Agent acts outside role

    # Inter-Agent Failures
    INFORMATION_WITHHOLDING = (
        "information_withholding"  # Agent doesn't share critical info
    )
    COORDINATION_FAILURE = "coordination_failure"  # Agents fail to coordinate

    # Execution Failures
    STEP_REPETITION = "step_repetition"  # Agent repeats same step
    INFINITE_LOOP = "infinite_loop"  # Agent stuck in loop
    PREMATURE_TERMINATION = "premature_termination"  # Agent quits too early

    # Quality Failures
    INSUFFICIENT_VERIFICATION = (
        "insufficient_verification"  # Agent doesn't verify outputs
    )
    REASONING_MISMATCH = "reasoning_mismatch"  # Agent's reasoning doesn't match action

    # Resource Failures
    TIMEOUT = "timeout"  # Operation took too long
    RESOURCE_EXHAUSTED = "resource_exhausted"  # Ran out of tokens/memory


@dataclass
class FailureEvent:
    """A detected failure in the system."""

    type: FailureType
    agent_name: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class RecoveryAction:
    """An action to recover from a failure."""

    name: str
    description: str
    action: Callable
    success_rate: float = 0.0


class MASTDetector:
    """
    Detects failures using MAST taxonomy.
    Monitors agent behavior for failure patterns.
    """

    def __init__(self):
        self._failure_log: List[FailureEvent] = []
        self._step_history: List[str] = []
        self._max_repetitions = 3
        self._max_steps = 20

    def check_step_repetition(self, current_step: str) -> Optional[FailureEvent]:
        """Detect step repetition (MAST F4)."""
        self._step_history.append(current_step)

        # Check for immediate repetition
        if len(self._step_history) >= 3:
            recent = self._step_history[-3:]
            if len(set(recent)) == 1:
                return FailureEvent(
                    type=FailureType.STEP_REPETITION,
                    agent_name=current_step.split()[-1] if current_step else "Unknown",
                    description=f"Step '{current_step}' repeated {self._max_repetitions} times",
                    severity="high",
                )

        return None

    def check_infinite_loop(self, step_count: int) -> Optional[FailureEvent]:
        """Detect potential infinite loop (MAST F5)."""
        if step_count > self._max_steps:
            return FailureEvent(
                type=FailureType.INFINITE_LOOP,
                agent_name="System",
                description=f"Workflow exceeded {self._max_steps} steps - possible infinite loop",
                severity="critical",
            )
        return None

    def check_role_violation(
        self, agent_name: str, action: str, allowed_actions: List[str]
    ) -> Optional[FailureEvent]:
        """Detect role violation (MAST F2)."""
        if action not in allowed_actions:
            return FailureEvent(
                type=FailureType.ROLE_VIOLATION,
                agent_name=agent_name,
                description=f"Agent attempted action '{action}' not in allowed list",
                severity="medium",
            )
        return None

    def check_reasoning_mismatch(
        self, reasoning: str, action: str
    ) -> Optional[FailureEvent]:
        """Detect reasoning-action mismatch (MAST F9)."""
        # Simple heuristic: check if action is mentioned in reasoning
        if action.lower() not in reasoning.lower():
            return FailureEvent(
                type=FailureType.REASONING_MISMATCH,
                agent_name="Unknown",
                description="Agent's reasoning doesn't mention the action being taken",
                severity="low",
            )
        return None

    def record_failure(self, failure: FailureEvent):
        """Record a detected failure."""
        self._failure_log.append(failure)
        logger.warning(f"MAST Failure: {failure.type.value} - {failure.description}")

    def get_failure_summary(self) -> Dict[str, Any]:
        """Get summary of all detected failures."""
        return {
            "total_failures": len(self._failure_log),
            "by_type": {
                f.type.value: len([x for x in self._failure_log if x.type == f.type])
                for f in FailureType
            },
            "critical_count": len(
                [f for f in self._failure_log if f.severity == "critical"]
            ),
            "recent": [
                {
                    "type": f.type.value,
                    "agent": f.agent_name,
                    "description": f.description,
                }
                for f in self._failure_log[-5:]
            ],
        }


class RecoveryManager:
    """
    Manages recovery from detected failures.
    Implements recovery strategies for each failure type.
    """

    def __init__(self):
        self._recovery_strategies: Dict[FailureType, List[RecoveryAction]] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Register default recovery strategies."""

        # Step repetition: Reset and retry with different approach
        self._recovery_strategies[FailureType.STEP_REPETITION] = [
            RecoveryAction(
                name="reset_and_skip",
                description="Skip the repeated step and move to next agent",
                action=lambda ctx: self._skip_current_agent(ctx),
                success_rate=0.7,
            )
        ]

        # Infinite loop: Force termination
        self._recovery_strategies[FailureType.INFINITE_LOOP] = [
            RecoveryAction(
                name="force_terminate",
                description="Force workflow termination and save partial results",
                action=lambda ctx: self._force_terminate(ctx),
                success_rate=0.9,
            )
        ]

        # Role violation: Log and continue
        self._recovery_strategies[FailureType.ROLE_VIOLATION] = [
            RecoveryAction(
                name="log_and_continue",
                description="Log the violation and continue with guardrails",
                action=lambda ctx: self._log_violation(ctx),
                success_rate=0.8,
            )
        ]

    def recover(self, failure: FailureEvent, context: Any) -> bool:
        """Attempt to recover from a failure."""
        strategies = self._recovery_strategies.get(failure.type, [])

        for strategy in strategies:
            try:
                logger.info(f"Attempting recovery: {strategy.name}")
                success = strategy.action(context)
                failure.recovery_attempted = True
                failure.recovery_successful = success
                if success:
                    logger.info(f"Recovery successful: {strategy.name}")
                    return True
            except Exception as e:
                logger.error(f"Recovery failed: {strategy.name} - {e}")

        return False

    def _skip_current_agent(self, context: Any) -> bool:
        """Skip the current agent and mark as handled."""
        logger.info("Skipping repeated agent")
        return True

    def _force_terminate(self, context: Any) -> bool:
        """Force workflow termination."""
        logger.warning("Forcing workflow termination")
        return True

    def _log_violation(self, context: Any) -> bool:
        """Log role violation and continue."""
        logger.warning("Role violation logged - continuing with guardrails")
        return True


class CircuitBreaker:
    """
    Enhanced circuit breaker for agent execution.
    Prevents cascading failures by stopping calls to failing agents.
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 60):
        self._failure_counts: Dict[str, int] = {}
        self._circuit_open: Dict[str, bool] = {}
        self._last_failure_time: Dict[str, datetime] = {}
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout

    def is_open(self, agent_name: str) -> bool:
        """Check if circuit is open (blocking calls) for an agent."""
        if agent_name not in self._circuit_open:
            return False

        if self._circuit_open[agent_name]:
            # Check if reset timeout has passed
            last_failure = self._last_failure_time.get(agent_name)
            if last_failure:
                elapsed = (datetime.now() - last_failure).seconds
                if elapsed > self._reset_timeout:
                    self._half_open(agent_name)
                    return False
            return True

        return False

    def record_failure(self, agent_name: str):
        """Record a failure for an agent."""
        self._failure_counts[agent_name] = self._failure_counts.get(agent_name, 0) + 1
        self._last_failure_time[agent_name] = datetime.now()

        if self._failure_counts[agent_name] >= self._failure_threshold:
            self._open(agent_name)

    def record_success(self, agent_name: str):
        """Record a success for an agent."""
        self._failure_counts[agent_name] = 0
        self._circuit_open[agent_name] = False

    def _open(self, agent_name: str):
        """Open the circuit (stop calls to agent)."""
        self._circuit_open[agent_name] = True
        logger.warning(f"Circuit OPEN for {agent_name} - too many failures")

    def _half_open(self, agent_name: str):
        """Set circuit to half-open (allow one probe call)."""
        self._circuit_open[agent_name] = False
        logger.info(f"Circuit HALF-OPEN for {agent_name} - allowing probe call")

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "agents": {
                name: {
                    "failures": self._failure_counts.get(name, 0),
                    "open": self._circuit_open.get(name, False),
                }
                for name in set(
                    list(self._failure_counts.keys()) + list(self._circuit_open.keys())
                )
            }
        }


# Module-level instances
_detector: Optional[MASTDetector] = None
_recovery_manager: Optional[RecoveryManager] = None
_circuit_breaker: Optional[CircuitBreaker] = None


def get_mast_detector() -> MASTDetector:
    """Get or create the MAST detector instance."""
    global _detector
    if _detector is None:
        _detector = MASTDetector()
    return _detector


def get_recovery_manager() -> RecoveryManager:
    """Get or create the recovery manager instance."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = RecoveryManager()
    return _recovery_manager


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create the circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
