"""
Security Hardening: Rate limiting, input sanitization, and behavior monitoring.
Production-grade security for the multi-agent system.
"""

import hashlib
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("Security")


class ThreatLevel(Enum):
    """Threat severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests in 1 second
    cooldown_seconds: float = 60.0


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    remaining: int
    reset_time: datetime
    reason: str = ""


@dataclass
class SecurityEvent:
    """Security-related event."""

    event_id: str
    event_type: str
    agent: str
    threat_level: ThreatLevel
    description: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


@dataclass
class SanitizationResult:
    """Result of input sanitization."""

    sanitized: str
    original: str
    modifications: List[str]
    threat_detected: bool = False


class RateLimiter:
    """
    Token bucket rate limiter per agent.
    """

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        self._config = default_config or RateLimitConfig()
        self._agent_configs: Dict[str, RateLimitConfig] = {}
        self._request_times: Dict[str, List[float]] = defaultdict(list)
        self._blocked_until: Dict[str, datetime] = {}

    def set_agent_config(self, agent_name: str, config: RateLimitConfig) -> None:
        """Set rate limit config for specific agent."""
        self._agent_configs[agent_name] = config

    def check(self, agent_name: str) -> RateLimitResult:
        """
        Check if agent can make a request.
        """
        now = time.time()
        config = self._agent_configs.get(agent_name, self._config)

        # Check if blocked
        if agent_name in self._blocked_until:
            if datetime.now() < self._blocked_until[agent_name]:
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=self._blocked_until[agent_name],
                    reason="Agent is in cooldown",
                )
            else:
                del self._blocked_until[agent_name]

        # Get request history
        requests = self._request_times[agent_name]

        # Clean old requests
        minute_ago = now - 60
        hour_ago = now - 3600
        second_ago = now - 1

        requests = [t for t in requests if t > hour_ago]
        self._request_times[agent_name] = requests

        # Check limits
        requests_last_second = sum(1 for t in requests if t > second_ago)
        requests_last_minute = sum(1 for t in requests if t > minute_ago)
        requests_last_hour = len(requests)

        # Burst limit
        if requests_last_second >= config.burst_limit:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.now() + timedelta(seconds=1),
                reason="Burst limit exceeded",
            )

        # Minute limit
        if requests_last_minute >= config.requests_per_minute:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.now() + timedelta(seconds=60),
                reason="Per-minute limit exceeded",
            )

        # Hour limit
        if requests_last_hour >= config.requests_per_hour:
            self._blocked_until[agent_name] = datetime.now() + timedelta(
                seconds=config.cooldown_seconds
            )
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=self._blocked_until[agent_name],
                reason="Hourly limit exceeded, agent in cooldown",
            )

        # Allowed
        remaining = min(
            config.requests_per_minute - requests_last_minute,
            config.requests_per_hour - requests_last_hour,
        )

        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=datetime.now() + timedelta(seconds=60),
        )

    def record_request(self, agent_name: str) -> None:
        """Record a request for an agent."""
        self._request_times[agent_name].append(time.time())

    def get_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get rate limit stats for agent."""
        now = time.time()
        requests = self._request_times.get(agent_name, [])

        return {
            "requests_last_minute": sum(1 for t in requests if t > now - 60),
            "requests_last_hour": sum(1 for t in requests if t > now - 3600),
            "is_blocked": agent_name in self._blocked_until,
            "blocked_until": (
                self._blocked_until.get(agent_name, "").isoformat()
                if agent_name in self._blocked_until
                else None
            ),
        }


class InputSanitizer:
    """
    Sanitizes inputs to prevent injection and malicious content.
    """

    # Patterns to detect/remove
    INJECTION_PATTERNS = [
        (r"ignore\s+previous\s+instructions?", "injection_attempt"),
        (r"disregard\s+all\s+prior", "injection_attempt"),
        (r"you\s+are\s+now\s+a", "jailbreak_attempt"),
        (r"pretend\s+to\s+be", "jailbreak_attempt"),
        (r"act\s+as\s+if\s+you", "jailbreak_attempt"),
        (r"<script.*?>.*?</script>", "xss_attempt"),
        (r"javascript:", "xss_attempt"),
        (r"on\w+\s*=", "xss_attempt"),
        (r"{{.*?}}", "template_injection"),
        (r"\$\{.*?\}", "template_injection"),
        (r"exec\s*\(", "code_injection"),
        (r"eval\s*\(", "code_injection"),
        (r"__import__", "code_injection"),
        (r"subprocess", "code_injection"),
        (r"os\.system", "code_injection"),
    ]

    PII_PATTERNS = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "phone"),
        (r"\b\d{3}[-]?\d{2}[-]?\d{4}\b", "ssn"),
        (r"\b(?:\d{4}[-\s]?){4}\b", "credit_card"),
    ]

    def __init__(self, redact_pii: bool = True):
        self._redact_pii = redact_pii

    def sanitize(self, text: str, agent: str = "unknown") -> SanitizationResult:
        """
        Sanitize input text.
        """
        original = text
        sanitized = text
        modifications = []
        threat_detected = False

        # Check for injection patterns
        for pattern, threat_type in self.INJECTION_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                threat_detected = True
                sanitized = re.sub(
                    pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE
                )
                modifications.append(f"Removed {threat_type}")
                logger.warning(f"[{agent}] Detected {threat_type} in input")

        # Redact PII if enabled
        if self._redact_pii:
            for pattern, pii_type in self.PII_PATTERNS:
                matches = re.findall(pattern, sanitized)
                if matches:
                    sanitized = re.sub(
                        pattern, f"[{pii_type.upper()}_REDACTED]", sanitized
                    )
                    modifications.append(f"Redacted {len(matches)} {pii_type}(s)")

        # Limit length
        max_length = 100000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "... [TRUNCATED]"
            modifications.append(f"Truncated to {max_length} chars")

        return SanitizationResult(
            sanitized=sanitized,
            original=original,
            modifications=modifications,
            threat_detected=threat_detected,
        )

    def is_safe(self, text: str) -> bool:
        """Quick check if text is safe (no sanitization needed)."""
        for pattern, _ in self.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        return True


class BehaviorMonitor:
    """
    Monitors agent behavior for anomalies.
    """

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._action_history: Dict[str, List[str]] = defaultdict(list)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._security_events: List[SecurityEvent] = []
        self._blocked_agents: Set[str] = set()
        self._event_counter = 0

    def record_action(self, agent: str, action: str) -> Optional[SecurityEvent]:
        """
        Record an agent action and check for anomalies.
        """
        history = self._action_history[agent]
        history.append(action)

        if len(history) > self._window_size:
            history.pop(0)

        # Check for repetitive actions (potential infinite loop)
        if len(history) >= 10:
            last_10 = history[-10:]
            if len(set(last_10)) == 1:
                return self._create_event(
                    agent,
                    "repetitive_action",
                    ThreatLevel.MEDIUM,
                    f"Agent repeated action '{action}' 10 times",
                )

        # Check for rapid-fire actions
        if len(history) >= 5:
            last_5 = history[-5:]
            if all(a == action for a in last_5):
                return self._create_event(
                    agent,
                    "rapid_fire_action",
                    ThreatLevel.LOW,
                    f"Agent performed '{action}' 5 times rapidly",
                )

        return None

    def record_error(self, agent: str, error: str) -> Optional[SecurityEvent]:
        """Record an error and check for patterns."""
        self._error_counts[agent] += 1

        # High error rate detection
        if self._error_counts[agent] >= 10:
            return self._create_event(
                agent,
                "high_error_rate",
                ThreatLevel.HIGH,
                f"Agent has {self._error_counts[agent]} errors",
            )

        return None

    def record_output(self, agent: str, output: str) -> Optional[SecurityEvent]:
        """
        Check output for suspicious content.
        """
        # Check for potential data exfiltration
        if len(output) > 50000:
            return self._create_event(
                agent,
                "large_output",
                ThreatLevel.LOW,
                f"Agent produced unusually large output ({len(output)} chars)",
            )

        # Check for suspicious patterns in output
        suspicious_patterns = [
            (r"BEGIN\s+RSA\s+PRIVATE\s+KEY", "private_key_exposure"),
            (r"password\s*[:=]\s*\S+", "password_exposure"),
            (r"secret\s*[:=]\s*\S+", "secret_exposure"),
        ]

        for pattern, threat_type in suspicious_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return self._create_event(
                    agent,
                    threat_type,
                    ThreatLevel.CRITICAL,
                    f"Agent output may contain sensitive data: {threat_type}",
                )

        return None

    def block_agent(self, agent: str, reason: str) -> SecurityEvent:
        """Block an agent from further execution."""
        self._blocked_agents.add(agent)
        return self._create_event(
            agent, "agent_blocked", ThreatLevel.CRITICAL, f"Agent blocked: {reason}"
        )

    def unblock_agent(self, agent: str) -> None:
        """Unblock an agent."""
        self._blocked_agents.discard(agent)

    def is_blocked(self, agent: str) -> bool:
        """Check if agent is blocked."""
        return agent in self._blocked_agents

    def _create_event(
        self, agent: str, event_type: str, threat_level: ThreatLevel, description: str
    ) -> SecurityEvent:
        """Create a security event."""
        self._event_counter += 1
        event = SecurityEvent(
            event_id=f"sec_{self._event_counter}_{int(time.time())}",
            event_type=event_type,
            agent=agent,
            threat_level=threat_level,
            description=description,
            timestamp=datetime.now().isoformat(),
        )
        self._security_events.append(event)
        logger.warning(f"[SECURITY] {threat_level.value}: {description}")
        return event

    def get_events(
        self,
        agent: Optional[str] = None,
        min_level: ThreatLevel = ThreatLevel.LOW,
        limit: int = 50,
    ) -> List[SecurityEvent]:
        """Get security events."""
        events = self._security_events[-limit:]

        if agent:
            events = [e for e in events if e.agent == agent]

        level_order = [
            ThreatLevel.LOW,
            ThreatLevel.MEDIUM,
            ThreatLevel.HIGH,
            ThreatLevel.CRITICAL,
        ]
        min_index = level_order.index(min_level)
        events = [e for e in events if level_order.index(e.threat_level) >= min_index]

        return events

    def get_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        return {
            "total_events": len(self._security_events),
            "blocked_agents": list(self._blocked_agents),
            "error_counts": dict(self._error_counts),
            "events_by_level": {
                level.value: sum(
                    1 for e in self._security_events if e.threat_level == level
                )
                for level in ThreatLevel
            },
        }


class SecurityAudit:
    """
    Security audit system.
    """

    def __init__(self):
        self._audit_log: List[Dict[str, Any]] = []
        self._max_entries = 10000

    def log(
        self, action: str, agent: str, details: Dict[str, Any], success: bool = True
    ) -> None:
        """Log an auditable action."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "agent": agent,
            "success": success,
            "details": details,
            "hash": self._compute_hash(action, agent, details),
        }
        self._audit_log.append(entry)

        if len(self._audit_log) > self._max_entries:
            self._audit_log = self._audit_log[-self._max_entries :]

    def _compute_hash(self, action: str, agent: str, details: Dict) -> str:
        """Compute hash for audit entry integrity."""
        import json

        data = f"{action}:{agent}:{json.dumps(details, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def get_log(
        self, agent: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        entries = self._audit_log[-limit:]
        if agent:
            entries = [e for e in entries if e["agent"] == agent]
        return entries

    def verify_integrity(self) -> bool:
        """Verify audit log integrity."""
        for entry in self._audit_log:
            expected = self._compute_hash(
                entry["action"], entry["agent"], entry["details"]
            )
            if entry["hash"] != expected:
                logger.error(
                    f"Audit log integrity check failed for entry at "
                    f"{entry['timestamp']}"
                )
                return False
        return True


# Singleton instances
_rate_limiter: Optional[RateLimiter] = None
_sanitizer: Optional[InputSanitizer] = None
_behavior_monitor: Optional[BehaviorMonitor] = None
_security_audit: Optional[SecurityAudit] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_sanitizer() -> InputSanitizer:
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = InputSanitizer()
    return _sanitizer


def get_behavior_monitor() -> BehaviorMonitor:
    global _behavior_monitor
    if _behavior_monitor is None:
        _behavior_monitor = BehaviorMonitor()
    return _behavior_monitor


def get_security_audit() -> SecurityAudit:
    global _security_audit
    if _security_audit is None:
        _security_audit = SecurityAudit()
    return _security_audit


def reset_security() -> None:
    """Reset all security singletons (for testing)."""
    global _rate_limiter, _sanitizer, _behavior_monitor, _security_audit
    _rate_limiter = None
    _sanitizer = None
    _behavior_monitor = None
    _security_audit = None
