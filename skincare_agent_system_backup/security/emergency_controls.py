"""
Emergency Controls and Fine-Grained Authorization.
Implements:
- Fine-Grained Scopes (Least Privilege)
- Data Security Filters (FGA)
- Universal Logout (Kill Switch)
- Behavioral Monitoring & Anomaly Detection
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("EmergencyControls")


class AccessLevel(Enum):
    """Access levels for fine-grained authorization."""

    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 3
    ADMIN = 4


@dataclass
class Scope:
    """Fine-grained scope definition."""

    resource: str  # e.g., "crm", "documents", "api"
    action: str  # e.g., "read", "write", "delete"
    filters: Dict[str, Any] = field(
        default_factory=dict
    )  # e.g., {"department": "sales"}

    def __str__(self) -> str:
        return f"mcp:{self.resource}:{self.action}"

    def matches(self, resource: str, action: str) -> bool:
        return self.resource == resource and self.action == action


@dataclass
class AgentPermissions:
    """Permissions assigned to an agent."""

    agent_id: str
    scopes: List[Scope] = field(default_factory=list)
    denied_scopes: List[Scope] = field(default_factory=list)
    max_requests_per_minute: int = 100
    max_data_access_per_hour: int = 1000
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    def has_scope(self, resource: str, action: str) -> bool:
        """Check if agent has specific scope."""
        if not self.is_active:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False

        # Check denials first
        for scope in self.denied_scopes:
            if scope.matches(resource, action):
                return False

        # Check grants
        for scope in self.scopes:
            if scope.matches(resource, action):
                return True

        return False


class FineGrainedAuth:
    """
    Fine-Grained Authorization (FGA) system.
    Enforces least privilege and data filtering.
    """

    def __init__(self):
        self._permissions: Dict[str, AgentPermissions] = {}
        self._data_filters: Dict[str, Callable] = {}

    def grant_permission(
        self,
        agent_id: str,
        resource: str,
        action: str,
        filters: Dict = None,
        max_requests: int = 100,
        max_data: int = 1000,
        ttl_seconds: int = None,
    ) -> AgentPermissions:
        """Grant fine-grained permission to agent."""
        if agent_id not in self._permissions:
            self._permissions[agent_id] = AgentPermissions(
                agent_id=agent_id,
                max_requests_per_minute=max_requests,
                max_data_access_per_hour=max_data,
            )

        scope = Scope(resource=resource, action=action, filters=filters or {})
        self._permissions[agent_id].scopes.append(scope)

        if ttl_seconds:
            self._permissions[agent_id].expires_at = time.time() + ttl_seconds

        logger.info(f"Granted {scope} to {agent_id}")
        return self._permissions[agent_id]

    def deny_permission(self, agent_id: str, resource: str, action: str):
        """Explicitly deny a permission (overrides grants)."""
        if agent_id not in self._permissions:
            self._permissions[agent_id] = AgentPermissions(agent_id=agent_id)

        scope = Scope(resource=resource, action=action)
        self._permissions[agent_id].denied_scopes.append(scope)
        logger.warning(f"Denied {scope} to {agent_id}")

    def check_permission(self, agent_id: str, resource: str, action: str) -> bool:
        """Check if agent has permission."""
        perms = self._permissions.get(agent_id)
        if not perms:
            logger.warning(f"No permissions defined for {agent_id}")
            return False
        return perms.has_scope(resource, action)

    def filter_data(self, agent_id: str, data: List[Dict], resource: str) -> List[Dict]:
        """Filter data based on agent's scope filters."""
        perms = self._permissions.get(agent_id)
        if not perms:
            return []

        # Find applicable scope
        for scope in perms.scopes:
            if scope.resource == resource and scope.filters:
                # Apply filters
                filtered = []
                for item in data:
                    matches = all(item.get(k) == v for k, v in scope.filters.items())
                    if matches:
                        filtered.append(item)
                return filtered

        return data

    def get_permissions(self, agent_id: str) -> Optional[AgentPermissions]:
        return self._permissions.get(agent_id)


@dataclass
class BehaviorProfile:
    """Baseline behavior profile for an agent."""

    agent_id: str
    avg_requests_per_minute: float = 10.0
    avg_data_access_per_hour: float = 100.0
    typical_resources: Set[str] = field(default_factory=set)
    anomaly_threshold: float = 3.0  # Standard deviations


@dataclass
class AgentActivity:
    """Tracks agent activity for monitoring."""

    agent_id: str
    request_timestamps: List[float] = field(default_factory=list)
    data_access_count: int = 0
    resources_accessed: Set[str] = field(default_factory=set)
    last_reset: float = field(default_factory=time.time)


class BehavioralMonitor:
    """
    Monitors agent behavior and detects anomalies.
    Triggers lockdown on suspicious activity.
    """

    def __init__(self):
        self._profiles: Dict[str, BehaviorProfile] = {}
        self._activity: Dict[str, AgentActivity] = {}
        self._alerts: List[Dict] = []

    def set_baseline(
        self,
        agent_id: str,
        avg_requests: float = 10.0,
        avg_data_access: float = 100.0,
        typical_resources: Set[str] = None,
    ):
        """Set baseline behavior profile for an agent."""
        self._profiles[agent_id] = BehaviorProfile(
            agent_id=agent_id,
            avg_requests_per_minute=avg_requests,
            avg_data_access_per_hour=avg_data_access,
            typical_resources=typical_resources or set(),
        )
        self._activity[agent_id] = AgentActivity(agent_id=agent_id)

    def record_request(self, agent_id: str, resource: str = None):
        """Record an agent request."""
        if agent_id not in self._activity:
            self._activity[agent_id] = AgentActivity(agent_id=agent_id)

        activity = self._activity[agent_id]
        now = time.time()

        # Clean old timestamps (keep last minute)
        activity.request_timestamps = [
            ts for ts in activity.request_timestamps if now - ts < 60
        ]
        activity.request_timestamps.append(now)

        if resource:
            activity.resources_accessed.add(resource)

    def record_data_access(self, agent_id: str, count: int = 1):
        """Record data access."""
        if agent_id not in self._activity:
            self._activity[agent_id] = AgentActivity(agent_id=agent_id)

        self._activity[agent_id].data_access_count += count

    def check_anomalies(self, agent_id: str) -> List[str]:
        """Check for behavioral anomalies."""
        anomalies = []
        profile = self._profiles.get(agent_id)
        activity = self._activity.get(agent_id)

        if not profile or not activity:
            return anomalies

        # Check request rate
        current_rate = len(activity.request_timestamps)
        expected = profile.avg_requests_per_minute
        threshold = profile.anomaly_threshold

        if current_rate > expected * threshold:
            anomaly = f"High request rate: {current_rate}/min (expected ~{expected})"
            anomalies.append(anomaly)
            self._record_alert(agent_id, "HIGH_REQUEST_RATE", anomaly)

        # Check data access
        if activity.data_access_count > profile.avg_data_access_per_hour * threshold:
            anomaly = f"Excessive data access: {activity.data_access_count} records"
            anomalies.append(anomaly)
            self._record_alert(agent_id, "EXCESSIVE_DATA_ACCESS", anomaly)

        # Check unusual resources
        if profile.typical_resources:
            unusual = activity.resources_accessed - profile.typical_resources
            if unusual:
                anomaly = f"Unusual resource access: {unusual}"
                anomalies.append(anomaly)
                self._record_alert(agent_id, "UNUSUAL_RESOURCE", anomaly)

        return anomalies

    def _record_alert(self, agent_id: str, alert_type: str, message: str):
        self._alerts.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
                "type": alert_type,
                "message": message,
            }
        )
        logger.warning(f"ALERT [{alert_type}] {agent_id}: {message}")

    def get_alerts(self) -> List[Dict]:
        return self._alerts.copy()

    def reset_activity(self, agent_id: str):
        """Reset activity tracking (e.g., after lockdown)."""
        if agent_id in self._activity:
            self._activity[agent_id] = AgentActivity(agent_id=agent_id)


class EmergencyController:
    """
    Emergency controls for agent system.
    Provides universal logout and kill switch functionality.
    """

    def __init__(self, fga: FineGrainedAuth = None, monitor: BehavioralMonitor = None):
        self.fga = fga or FineGrainedAuth()
        self.monitor = monitor or BehavioralMonitor()
        self._revoked_agents: Set[str] = set()
        self._lockdown_log: List[Dict] = []
        self._global_lockdown = False

    def universal_logout(self, agent_id: str, reason: str = "Manual revocation"):
        """
        Instantly revoke all access for an agent.
        Kill switch functionality.
        """
        # Revoke permissions
        if agent_id in self.fga._permissions:
            self.fga._permissions[agent_id].is_active = False

        # Add to revoked set
        self._revoked_agents.add(agent_id)

        # Reset activity
        self.monitor.reset_activity(agent_id)

        # Log action
        self._lockdown_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "UNIVERSAL_LOGOUT",
                "agent_id": agent_id,
                "reason": reason,
            }
        )

        logger.critical(f"UNIVERSAL LOGOUT: {agent_id} - {reason}")

    def global_lockdown(self, reason: str = "System-wide threat detected"):
        """
        Lock down ALL agents immediately.
        Nuclear option for critical situations.
        """
        self._global_lockdown = True

        # Deactivate all permissions
        for perms in self.fga._permissions.values():
            perms.is_active = False

        self._lockdown_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "GLOBAL_LOCKDOWN",
                "agent_id": "*",
                "reason": reason,
            }
        )

        logger.critical(f"GLOBAL LOCKDOWN ACTIVATED: {reason}")

    def lift_lockdown(self, agent_id: str = None):
        """Lift lockdown for specific agent or globally."""
        if agent_id:
            if agent_id in self._revoked_agents:
                self._revoked_agents.remove(agent_id)
            if agent_id in self.fga._permissions:
                self.fga._permissions[agent_id].is_active = True
            logger.info(f"Lockdown lifted for {agent_id}")
        else:
            self._global_lockdown = False
            for perms in self.fga._permissions.values():
                perms.is_active = True
            self._revoked_agents.clear()
            logger.info("Global lockdown lifted")

    def is_agent_active(self, agent_id: str) -> bool:
        """Check if agent is currently active (not locked down)."""
        if self._global_lockdown:
            return False
        if agent_id in self._revoked_agents:
            return False
        perms = self.fga.get_permissions(agent_id)
        return perms.is_active if perms else False

    def auto_lockdown_check(self, agent_id: str) -> bool:
        """
        Automatically check for anomalies and lockdown if needed.
        Returns True if agent was locked down.
        """
        anomalies = self.monitor.check_anomalies(agent_id)

        if len(anomalies) >= 2:  # Multiple anomalies = lockdown
            reason = f"Auto-lockdown: {'; '.join(anomalies)}"
            self.universal_logout(agent_id, reason)
            return True

        return False

    def get_lockdown_log(self) -> List[Dict]:
        return self._lockdown_log.copy()


# Singleton instances
_fga: Optional[FineGrainedAuth] = None
_monitor: Optional[BehavioralMonitor] = None
_emergency: Optional[EmergencyController] = None


def get_fga() -> FineGrainedAuth:
    global _fga
    if _fga is None:
        _fga = FineGrainedAuth()
    return _fga


def get_behavioral_monitor() -> BehavioralMonitor:
    global _monitor
    if _monitor is None:
        _monitor = BehavioralMonitor()
    return _monitor


def get_emergency_controller() -> EmergencyController:
    global _emergency
    if _emergency is None:
        _emergency = EmergencyController(get_fga(), get_behavioral_monitor())
    return _emergency
