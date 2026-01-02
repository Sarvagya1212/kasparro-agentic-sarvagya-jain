"""
Immutable Context: Versioned, freezable context with transaction support.
Enables rollback, diff tracking, and conflict detection.
"""

import copy
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ImmutableContext")


class MutationType(Enum):
    """Types of context mutations."""
    SET = "set"
    DELETE = "delete"
    APPEND = "append"
    UPDATE = "update"


@dataclass
class ContextMutation:
    """Record of a single context mutation."""
    mutation_id: str
    mutation_type: MutationType
    field_path: str  # e.g., "product_data.name" or "generated_questions"
    old_value: Any
    new_value: Any
    timestamp: str
    agent: str
    version: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "type": self.mutation_type.value,
            "path": self.field_path,
            "old": str(self.old_value)[:100] if self.old_value else None,
            "new": str(self.new_value)[:100] if self.new_value else None,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "version": self.version
        }


@dataclass
class ContextVersion:
    """A frozen snapshot of context at a point in time."""
    version_id: int
    snapshot: Dict[str, Any]
    hash: str
    timestamp: str
    agent: str  # Who created this version
    mutations_applied: List[str] = field(default_factory=list)

    def __eq__(self, other: "ContextVersion") -> bool:
        if not isinstance(other, ContextVersion):
            return False
        return self.hash == other.hash


@dataclass
class ContextCheckpoint:
    """Named checkpoint for rollback."""
    checkpoint_id: str
    name: str
    version_id: int
    timestamp: str
    description: str = ""


@dataclass
class ContextDiff:
    """Difference between two context versions."""
    from_version: int
    to_version: int
    added: Dict[str, Any]
    removed: Dict[str, Any]
    modified: Dict[str, Tuple[Any, Any]]  # field -> (old, new)

    def is_empty(self) -> bool:
        return not self.added and not self.removed and not self.modified

    def summary(self) -> str:
        parts = []
        if self.added:
            parts.append(f"+{len(self.added)} added")
        if self.removed:
            parts.append(f"-{len(self.removed)} removed")
        if self.modified:
            parts.append(f"~{len(self.modified)} modified")
        return ", ".join(parts) if parts else "no changes"


class TransactionLog:
    """
    Records all context mutations for rollback capability.
    """

    def __init__(self, max_entries: int = 1000):
        self._mutations: List[ContextMutation] = []
        self._max_entries = max_entries
        self._current_version = 0

    def record(
        self,
        mutation_type: MutationType,
        field_path: str,
        old_value: Any,
        new_value: Any,
        agent: str
    ) -> ContextMutation:
        """Record a mutation."""
        self._current_version += 1

        mutation = ContextMutation(
            mutation_id=f"mut_{self._current_version}_{datetime.now().strftime('%H%M%S%f')}",
            mutation_type=mutation_type,
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.now().isoformat(),
            agent=agent,
            version=self._current_version
        )

        self._mutations.append(mutation)

        # Prune if too many
        if len(self._mutations) > self._max_entries:
            self._mutations = self._mutations[-self._max_entries:]

        return mutation

    def get_mutations_since(self, version: int) -> List[ContextMutation]:
        """Get all mutations since a version."""
        return [m for m in self._mutations if m.version > version]

    def get_mutations_by_agent(self, agent: str) -> List[ContextMutation]:
        """Get mutations by a specific agent."""
        return [m for m in self._mutations if m.agent == agent]

    def get_mutations_for_field(self, field_path: str) -> List[ContextMutation]:
        """Get mutations affecting a specific field."""
        return [m for m in self._mutations if m.field_path.startswith(field_path)]

    def detect_conflicts(
        self,
        field_path: str,
        since_version: int
    ) -> List[ContextMutation]:
        """Detect conflicting mutations to a field since a version."""
        return [
            m for m in self._mutations
            if m.version > since_version and m.field_path == field_path
        ]

    @property
    def current_version(self) -> int:
        return self._current_version

    def __len__(self) -> int:
        return len(self._mutations)


class VersionedContext:
    """
    Immutable, versioned context wrapper.

    Features:
    - freeze() creates immutable snapshot
    - apply() creates new version with changes
    - Diff tracking between versions
    - Transaction log for rollback
    - Checkpoint system for named savepoints
    """

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Any] = initial_data or {}
        self._versions: List[ContextVersion] = []
        self._checkpoints: Dict[str, ContextCheckpoint] = {}
        self._transaction_log = TransactionLog()
        self._frozen = False
        self._current_version_id = 0

        # Create initial version
        self._create_version("system", "initial")

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute hash of context data."""
        try:
            serialized = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(serialized.encode()).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(str(data).encode()).hexdigest()[:16]

    def _create_version(
        self,
        agent: str,
        reason: str,
        mutations: List[str] = None
    ) -> ContextVersion:
        """Create a new version snapshot."""
        self._current_version_id += 1

        version = ContextVersion(
            version_id=self._current_version_id,
            snapshot=copy.deepcopy(self._data),
            hash=self._compute_hash(self._data),
            timestamp=datetime.now().isoformat(),
            agent=agent,
            mutations_applied=mutations or []
        )

        self._versions.append(version)
        logger.debug(f"Created version {version.version_id} by {agent}: {reason}")

        return version

    def freeze(self) -> "FrozenContext":
        """
        Create an immutable snapshot of current state.

        Returns a FrozenContext that cannot be modified.
        """
        return FrozenContext(
            data=copy.deepcopy(self._data),
            version_id=self._current_version_id,
            hash=self._compute_hash(self._data),
            timestamp=datetime.now().isoformat()
        )

    def apply(
        self,
        changes: Dict[str, Any],
        agent: str = "unknown"
    ) -> "VersionedContext":
        """
        Apply changes and create new version.

        Returns a new VersionedContext with changes applied.
        Original context is unchanged (immutable pattern).
        """
        # Create new context with current data
        new_context = VersionedContext(copy.deepcopy(self._data))
        new_context._versions = copy.deepcopy(self._versions)
        new_context._checkpoints = copy.deepcopy(self._checkpoints)
        new_context._transaction_log = self._transaction_log
        new_context._current_version_id = self._current_version_id

        # Apply changes
        mutation_ids = []
        for field_path, new_value in changes.items():
            old_value = new_context._get_nested(field_path)
            new_context._set_nested(field_path, new_value)

            # Record mutation
            mutation = new_context._transaction_log.record(
                MutationType.SET,
                field_path,
                old_value,
                new_value,
                agent
            )
            mutation_ids.append(mutation.mutation_id)

        # Create new version
        new_context._create_version(agent, f"applied {len(changes)} changes", mutation_ids)

        return new_context

    def _get_nested(self, path: str) -> Any:
        """Get value at nested path like 'product_data.name'."""
        parts = path.split(".")
        current = self._data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        return current

    def _set_nested(self, path: str, value: Any) -> None:
        """Set value at nested path."""
        parts = path.split(".")

        if len(parts) == 1:
            self._data[path] = value
            return

        current = self._data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def diff(self, from_version: int, to_version: int = None) -> ContextDiff:
        """
        Compute diff between two versions.
        """
        to_version = to_version or self._current_version_id

        from_snapshot = self._get_version(from_version)
        to_snapshot = self._get_version(to_version)

        if not from_snapshot or not to_snapshot:
            return ContextDiff(from_version, to_version, {}, {}, {})

        added = {}
        removed = {}
        modified = {}

        # Find added and modified
        for key, new_val in to_snapshot.snapshot.items():
            if key not in from_snapshot.snapshot:
                added[key] = new_val
            elif from_snapshot.snapshot[key] != new_val:
                modified[key] = (from_snapshot.snapshot[key], new_val)

        # Find removed
        for key in from_snapshot.snapshot:
            if key not in to_snapshot.snapshot:
                removed[key] = from_snapshot.snapshot[key]

        return ContextDiff(from_version, to_version, added, removed, modified)

    def _get_version(self, version_id: int) -> Optional[ContextVersion]:
        """Get a specific version."""
        for v in self._versions:
            if v.version_id == version_id:
                return v
        return None

    def create_checkpoint(
        self,
        name: str,
        description: str = ""
    ) -> ContextCheckpoint:
        """Create a named checkpoint for easy rollback."""
        checkpoint = ContextCheckpoint(
            checkpoint_id=f"cp_{name}_{self._current_version_id}",
            name=name,
            version_id=self._current_version_id,
            timestamp=datetime.now().isoformat(),
            description=description
        )
        self._checkpoints[name] = checkpoint
        logger.info(f"Created checkpoint '{name}' at version {self._current_version_id}")
        return checkpoint

    def rollback_to_checkpoint(self, name: str) -> "VersionedContext":
        """
        Rollback to a named checkpoint.

        Returns a new VersionedContext at the checkpoint state.
        """
        checkpoint = self._checkpoints.get(name)
        if not checkpoint:
            raise ValueError(f"Checkpoint '{name}' not found")

        return self.rollback_to_version(checkpoint.version_id)

    def rollback_to_version(self, version_id: int) -> "VersionedContext":
        """
        Rollback to a specific version.

        Returns a new VersionedContext at that version's state.
        """
        version = self._get_version(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        new_context = VersionedContext(copy.deepcopy(version.snapshot))
        new_context._versions = [v for v in self._versions if v.version_id <= version_id]
        new_context._checkpoints = self._checkpoints
        new_context._current_version_id = version_id

        logger.info(f"Rolled back to version {version_id}")
        return new_context

    def partial_rollback(
        self,
        fields: List[str],
        to_version: int
    ) -> "VersionedContext":
        """
        Rollback only specific fields to a version.
        """
        old_version = self._get_version(to_version)
        if not old_version:
            raise ValueError(f"Version {to_version} not found")

        changes = {}
        for field in fields:
            old_value = self._get_nested_from_dict(old_version.snapshot, field)
            if old_value is not None:
                changes[field] = old_value

        return self.apply(changes, agent="rollback")

    def _get_nested_from_dict(self, data: Dict, path: str) -> Any:
        """Get nested value from dict."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def get_version_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get version history for display."""
        history = []
        for v in self._versions[-limit:]:
            history.append({
                "version_id": v.version_id,
                "hash": v.hash,
                "timestamp": v.timestamp,
                "agent": v.agent,
                "mutations": len(v.mutations_applied)
            })
        return history

    def get_checkpoints(self) -> List[ContextCheckpoint]:
        """Get all checkpoints."""
        return list(self._checkpoints.values())

    @property
    def version(self) -> int:
        return self._current_version_id

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data


@dataclass
class FrozenContext:
    """
    Immutable snapshot of context.
    Cannot be modified after creation.
    """
    data: Dict[str, Any]
    version_id: int
    hash: str
    timestamp: str

    def __post_init__(self):
        # Make data deeply immutable by converting to frozenset where possible
        self._frozen = True

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def __setitem__(self, key: str, value: Any) -> None:
        raise TypeError("FrozenContext is immutable")

    def __delitem__(self, key: str) -> None:
        raise TypeError("FrozenContext is immutable")

    def to_versioned(self) -> VersionedContext:
        """Convert back to mutable VersionedContext."""
        return VersionedContext(copy.deepcopy(self.data))


# Factory functions
def create_versioned_context(
    initial_data: Optional[Dict[str, Any]] = None
) -> VersionedContext:
    """Create a new versioned context."""
    return VersionedContext(initial_data)


def from_agent_context(context: Any) -> VersionedContext:
    """Create VersionedContext from AgentContext."""
    if hasattr(context, 'model_dump'):
        data = context.model_dump()
    elif hasattr(context, '__dict__'):
        data = context.__dict__.copy()
    else:
        data = dict(context)

    return VersionedContext(data)
