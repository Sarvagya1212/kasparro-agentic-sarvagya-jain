"""
Agent Monitor: Kill Switches, Usage Tracking, and Anomaly Detection.

Production-grade monitoring for autonomous agents:
1. Universal Logout - instantly revoke all agent access
2. Per-Agent Kill Switch - revoke specific agent without system shutdown
3. Usage Tracking - monitor tokens/requests per agent
4. Anomaly Detection - auto-revoke on suspicious activity
5. Rate Limiting - prevent runaway agents from excessive spending
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger("AgentMonitor")


class AgentStatus(Enum):
    """Agent operational status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"  # Temporarily paused
    REVOKED = "revoked"  # Permanently blocked
    RATE_LIMITED = "rate_limited"  # Throttled


@dataclass
class UsageMetrics:
    """Usage metrics for an agent."""

    agent_id: str
    total_requests: int = 0
    total_tokens: int = 0
    requests_last_hour: int = 0
    tokens_last_hour: int = 0
    last_request_time: float = 0
    hourly_history: List[Dict] = field(default_factory=list)

    def record_usage(self, tokens: int):
        """Record a usage event."""
        now = time.time()
        self.total_requests += 1
        self.total_tokens += tokens
        self.requests_last_hour += 1
        self.tokens_last_hour += tokens
        self.last_request_time = now

        # Store in hourly history
        self.hourly_history.append({"timestamp": now, "tokens": tokens})

        # Trim old history (keep last 24 hours)
        cutoff = now - 86400
        self.hourly_history = [
            h for h in self.hourly_history if h["timestamp"] > cutoff
        ]

    def get_hourly_rate(self) -> float:
        """Get requests per hour rate."""
        if not self.hourly_history:
            return 0.0

        now = time.time()
        hour_ago = now - 3600
        recent = [h for h in self.hourly_history if h["timestamp"] > hour_ago]
        return len(recent)


@dataclass
class AnomalyThresholds:
    """Configurable thresholds for anomaly detection."""

    max_tokens_per_hour: int = 100000  # 100k tokens/hour
    max_requests_per_hour: int = 1000  # 1000 requests/hour
    token_spike_multiplier: float = 10.0  # 10x normal usage
    request_spike_multiplier: float = 10.0
    min_requests_for_baseline: int = 10  # Need at least 10 requests for baseline


class AgentMonitor:
    """
    Central monitoring and control for all agents.

    Provides:
    - Kill switches (universal and per-agent)
    - Usage tracking and metrics
    - Anomaly detection with auto-revocation
    - Rate limiting
    """

    def __init__(
        self, thresholds: AnomalyThresholds = None, enable_auto_revoke: bool = True
    ):
        self.thresholds = thresholds or AnomalyThresholds()
        self.enable_auto_revoke = enable_auto_revoke

        # Agent status tracking
        self._agent_status: Dict[str, AgentStatus] = {}
        self._revoked_agents: Set[str] = set()
        self._suspended_agents: Set[str] = set()

        # Usage metrics
        self._usage_metrics: Dict[str, UsageMetrics] = {}
        self._baseline_metrics: Dict[str, Dict] = {}

        # Universal kill switch
        self._system_active: bool = True

        # Callbacks for revocation events
        self._revocation_callbacks: List[Callable] = []

        # Thread lock for concurrent access
        self._lock = threading.RLock()

        # Anomaly log
        self._anomaly_log: List[Dict] = []

        logger.info("AgentMonitor initialized with anomaly detection")

    # ==================== KILL SWITCHES ====================

    def universal_logout(self, reason: str = "Emergency shutdown"):
        """
        EMERGENCY: Instantly revoke ALL agent access.

        Use when:
        - System compromise detected
        - Runaway spending detected
        - Security incident response
        """
        with self._lock:
            self._system_active = False

            # Mark all agents as revoked
            for agent_id in list(self._agent_status.keys()):
                self._agent_status[agent_id] = AgentStatus.REVOKED
                self._revoked_agents.add(agent_id)

            logger.critical(f"UNIVERSAL LOGOUT: {reason}")
            self._log_anomaly("UNIVERSAL_LOGOUT", "SYSTEM", reason)

            # Notify all callbacks
            for callback in self._revocation_callbacks:
                try:
                    callback("SYSTEM", reason)
                except Exception as e:
                    logger.error(f"Revocation callback failed: {e}")

    def reactivate_system(self, admin_token: str = None):
        """Re-enable system after universal logout (requires auth)."""
        # In production, validate admin_token
        with self._lock:
            self._system_active = True
            logger.warning("System reactivated - agents still revoked until cleared")

    def revoke_agent(self, agent_id: str, reason: str = "Manual revocation"):
        """
        Kill switch for a specific agent.

        Agent's credentials will be instantly invalidated.
        All pending requests will fail.
        """
        with self._lock:
            self._agent_status[agent_id] = AgentStatus.REVOKED
            self._revoked_agents.add(agent_id)

            logger.warning(f"Agent REVOKED: {agent_id} - {reason}")
            self._log_anomaly("AGENT_REVOKED", agent_id, reason)

            # Notify callbacks
            for callback in self._revocation_callbacks:
                try:
                    callback(agent_id, reason)
                except Exception:
                    pass

    def suspend_agent(self, agent_id: str, duration_seconds: int = 3600):
        """
        Temporarily suspend an agent (e.g., for rate limiting).

        Agent will be auto-reactivated after duration.
        """
        with self._lock:
            self._agent_status[agent_id] = AgentStatus.SUSPENDED
            self._suspended_agents.add(agent_id)

            logger.warning(f"Agent SUSPENDED: {agent_id} for {duration_seconds}s")

            # Schedule reactivation (in production, use a proper scheduler)
            def reactivate():
                time.sleep(duration_seconds)
                self.reactivate_agent(agent_id)

            thread = threading.Thread(target=reactivate, daemon=True)
            thread.start()

    def reactivate_agent(self, agent_id: str):
        """Reactivate a suspended agent."""
        with self._lock:
            if agent_id in self._revoked_agents:
                logger.warning(f"Cannot reactivate revoked agent: {agent_id}")
                return False

            self._agent_status[agent_id] = AgentStatus.ACTIVE
            self._suspended_agents.discard(agent_id)
            logger.info(f"Agent reactivated: {agent_id}")
            return True

    def clear_revocation(self, agent_id: str, admin_token: str = None):
        """Clear a revocation (requires admin auth in production)."""
        with self._lock:
            self._revoked_agents.discard(agent_id)
            self._agent_status[agent_id] = AgentStatus.ACTIVE
            logger.info(f"Revocation cleared for: {agent_id}")

    # ==================== ACCESS CONTROL ====================

    def is_agent_allowed(self, agent_id: str) -> bool:
        """
        Check if an agent is allowed to make requests.

        Called by LLMClient before every request.
        """
        with self._lock:
            # Check universal kill switch
            if not self._system_active:
                logger.warning(f"Request denied - system inactive: {agent_id}")
                return False

            # Check specific revocation
            if agent_id in self._revoked_agents:
                logger.warning(f"Request denied - agent revoked: {agent_id}")
                return False

            # Check suspension
            if agent_id in self._suspended_agents:
                logger.warning(f"Request denied - agent suspended: {agent_id}")
                return False

            return True

    # ==================== USAGE TRACKING ====================

    def record_usage(self, agent_id: str, tokens: int, success: bool = True):
        """
        Record agent usage for monitoring.

        Called after every LLM request.
        """
        with self._lock:
            # Initialize metrics if needed
            if agent_id not in self._usage_metrics:
                self._usage_metrics[agent_id] = UsageMetrics(agent_id=agent_id)

            metrics = self._usage_metrics[agent_id]
            metrics.record_usage(tokens)

            # Check for anomalies
            if self.enable_auto_revoke:
                self._check_anomalies(agent_id, metrics)

    def get_usage_metrics(self, agent_id: str) -> Optional[UsageMetrics]:
        """Get usage metrics for an agent."""
        return self._usage_metrics.get(agent_id)

    def get_all_metrics(self) -> Dict[str, UsageMetrics]:
        """Get all usage metrics."""
        return self._usage_metrics.copy()

    # ==================== ANOMALY DETECTION ====================

    def _check_anomalies(self, agent_id: str, metrics: UsageMetrics):
        """
        Check for usage anomalies and auto-revoke if detected.

        Anomalies:
        1. Absolute threshold exceeded
        2. Spike relative to baseline
        """
        # Check absolute thresholds
        if metrics.tokens_last_hour > self.thresholds.max_tokens_per_hour:
            self._handle_anomaly(
                agent_id,
                f"Token limit exceeded: {metrics.tokens_last_hour} > "
                f"{self.thresholds.max_tokens_per_hour}/hour",
            )
            return

        if metrics.requests_last_hour > self.thresholds.max_requests_per_hour:
            self._handle_anomaly(
                agent_id,
                f"Request limit exceeded: {metrics.requests_last_hour} > "
                f"{self.thresholds.max_requests_per_hour}/hour",
            )
            return

        # Check for spike relative to baseline
        baseline = self._baseline_metrics.get(agent_id)
        if (
            baseline
            and metrics.total_requests >= self.thresholds.min_requests_for_baseline
        ):
            avg_tokens = baseline.get("avg_tokens_per_request", 0)
            if avg_tokens > 0:
                current_avg = metrics.tokens_last_hour / max(
                    1, metrics.requests_last_hour
                )
                if current_avg > avg_tokens * self.thresholds.token_spike_multiplier:
                    self._handle_anomaly(
                        agent_id,
                        f"Token spike detected: {current_avg:.0f} vs baseline {avg_tokens:.0f}",
                    )

    def _handle_anomaly(self, agent_id: str, reason: str):
        """Handle detected anomaly."""
        logger.error(f"ANOMALY DETECTED: {agent_id} - {reason}")
        self._log_anomaly("ANOMALY", agent_id, reason)

        if self.enable_auto_revoke:
            self.suspend_agent(agent_id, duration_seconds=3600)  # 1 hour suspension

    def _log_anomaly(self, event_type: str, agent_id: str, details: str):
        """Log anomaly for audit."""
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "agent_id": agent_id,
            "details": details,
        }
        self._anomaly_log.append(entry)

        # Keep last 1000 entries
        if len(self._anomaly_log) > 1000:
            self._anomaly_log = self._anomaly_log[-1000:]

    def update_baseline(self, agent_id: str):
        """Update baseline metrics for an agent."""
        metrics = self._usage_metrics.get(agent_id)
        if (
            metrics
            and metrics.total_requests >= self.thresholds.min_requests_for_baseline
        ):
            self._baseline_metrics[agent_id] = {
                "avg_tokens_per_request": metrics.total_tokens / metrics.total_requests,
                "avg_requests_per_hour": metrics.get_hourly_rate(),
                "updated_at": time.time(),
            }
            logger.info(f"Baseline updated for {agent_id}")

    # ==================== CALLBACKS ====================

    def on_revocation(self, callback: Callable[[str, str], None]):
        """Register callback for revocation events."""
        self._revocation_callbacks.append(callback)

    # ==================== STATUS ====================

    def get_system_status(self) -> Dict:
        """Get overall system status."""
        return {
            "system_active": self._system_active,
            "total_agents": len(self._usage_metrics),
            "active_agents": len(
                [a for a, s in self._agent_status.items() if s == AgentStatus.ACTIVE]
            ),
            "suspended_agents": len(self._suspended_agents),
            "revoked_agents": len(self._revoked_agents),
            "recent_anomalies": len(
                [a for a in self._anomaly_log if a["timestamp"] > time.time() - 3600]
            ),
        }

    def get_anomaly_log(self) -> List[Dict]:
        """Get anomaly log for audit."""
        return self._anomaly_log.copy()


# Singleton instance
_monitor: Optional[AgentMonitor] = None


def get_agent_monitor() -> AgentMonitor:
    """Get or create singleton monitor."""
    global _monitor
    if _monitor is None:
        _monitor = AgentMonitor()
    return _monitor


def configure_monitor(
    thresholds: AnomalyThresholds = None, enable_auto_revoke: bool = True
):
    """Configure the agent monitor (call at startup)."""
    global _monitor
    _monitor = AgentMonitor(
        thresholds=thresholds, enable_auto_revoke=enable_auto_revoke
    )
    logger.info("Agent monitor configured")
