"""
Memory System: Differentiated memory types for coherent long interactions.
Includes Working Memory, Knowledge Base, Episodic Memory, and Context Compression.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Memory")


@dataclass
class WorkingMemory:
    """
    Short-term memory for immediate task context.
    Auto-clears between workflow runs.
    """

    current_task: Optional[str] = None
    active_parameters: Dict[str, Any] = field(default_factory=dict)
    search_context: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: List[Any] = field(default_factory=list)
    _created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def set_task(self, task: str, parameters: Dict[str, Any] = None):
        """Set current task with parameters."""
        self.current_task = task
        self.active_parameters = parameters or {}
        logger.info(f"Working memory: Task set to '{task}'")

    def add_result(self, result: Any):
        """Add intermediate result."""
        self.intermediate_results.append(result)

    def clear(self):
        """Clear working memory for new workflow."""
        self.current_task = None
        self.active_parameters = {}
        self.search_context = {}
        self.intermediate_results = []
        self._created_at = datetime.now().isoformat()
        logger.info("Working memory cleared")


@dataclass
class Episode:
    """A single interaction episode."""
    agent: str
    action: str
    outcome: str  # "success" or "failure"
    context_summary: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class EpisodicMemory:
    """
    Records past interaction outcomes for learning.
    Enables retrieval of similar past episodes.
    """

    def __init__(self, max_episodes: int = 100):
        self.episodes: List[Episode] = []
        self.max_episodes = max_episodes

    def add_episode(
        self,
        agent: str,
        action: str,
        outcome: str,
        context_summary: str,
        metadata: Dict[str, Any] = None
    ):
        """Record a new episode."""
        episode = Episode(
            agent=agent,
            action=action,
            outcome=outcome,
            context_summary=context_summary,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        self.episodes.append(episode)

        # Trim old episodes if exceeding max
        if len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes:]

        logger.info(f"Episode recorded: {agent}/{action} -> {outcome}")

    def get_similar_episodes(
        self,
        agent: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 5
    ) -> List[Episode]:
        """Retrieve similar past episodes."""
        filtered = self.episodes

        if agent:
            filtered = [e for e in filtered if e.agent == agent]
        if action:
            filtered = [e for e in filtered if e.action == action]

        return filtered[-limit:]

    def get_success_rate(self, agent: str) -> float:
        """Get success rate for an agent."""
        agent_episodes = [e for e in self.episodes if e.agent == agent]
        if not agent_episodes:
            return 0.0

        successes = sum(1 for e in agent_episodes if e.outcome == "success")
        return successes / len(agent_episodes)

    def to_dict(self) -> List[Dict]:
        """Convert to serializable format."""
        return [
            {
                "agent": e.agent,
                "action": e.action,
                "outcome": e.outcome,
                "context_summary": e.context_summary,
                "timestamp": e.timestamp,
                "metadata": e.metadata
            }
            for e in self.episodes
        ]

    @classmethod
    def from_dict(cls, data: List[Dict]) -> "EpisodicMemory":
        """Load from serialized format."""
        memory = cls()
        for item in data:
            memory.episodes.append(Episode(**item))
        return memory


class KnowledgeBase:
    """
    Long-term persistent memory for domain rules and user preferences.
    Loaded from/saved to JSON file.
    """

    def __init__(self, storage_path: str = "data/knowledge_base.json"):
        self.storage_path = Path(storage_path)
        self.domain_rules: Dict[str, Any] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.product_catalog: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load knowledge base from file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.domain_rules = data.get("domain_rules", {})
                    self.user_preferences = data.get("user_preferences", {})
                    self.product_catalog = data.get("product_catalog", {})
                logger.info(f"Knowledge base loaded from {self.storage_path}")
            except Exception as e:
                logger.warning(f"Failed to load knowledge base: {e}")
        else:
            self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize with default domain rules."""
        self.domain_rules = {
            "min_faq_questions": 15,
            "required_product_fields": ["name", "brand", "key_ingredients"],
            "max_retry_attempts": 3,
            "validation_thresholds": {
                "min_benefits": 2,
                "min_question_length": 10
            }
        }
        self.user_preferences = {
            "output_format": "json",
            "include_comparison": True,
            "language": "en"
        }
        self.save()

    def save(self):
        """Persist knowledge base to file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "domain_rules": self.domain_rules,
            "user_preferences": self.user_preferences,
            "product_catalog": self.product_catalog,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Knowledge base saved to {self.storage_path}")

    def get_rule(self, key: str, default: Any = None) -> Any:
        """Get a domain rule."""
        return self.domain_rules.get(key, default)

    def set_preference(self, key: str, value: Any):
        """Set a user preference."""
        self.user_preferences[key] = value
        self.save()


class ContextCompressor:
    """
    Compresses long conversation/decision histories.
    Retains key information while reducing token count.
    """

    @staticmethod
    def compress(
        history: List[Dict[str, Any]],
        max_items: int = 10,
        summary_threshold: int = 20
    ) -> Dict[str, Any]:
        """
        Compress history to manageable size.

        Args:
            history: List of history items (decisions, steps, etc.)
            max_items: Maximum items to keep in detail
            summary_threshold: Threshold to trigger summarization

        Returns:
            Compressed history with summary
        """
        if len(history) <= max_items:
            return {
                "type": "full",
                "items": history,
                "count": len(history)
            }

        # Keep recent items in detail
        recent = history[-max_items:]

        # Summarize older items
        older = history[:-max_items]
        summary = ContextCompressor._summarize(older)

        return {
            "type": "compressed",
            "summary": summary,
            "recent_items": recent,
            "total_count": len(history),
            "summarized_count": len(older)
        }

    @staticmethod
    def _summarize(items: List[Dict[str, Any]]) -> str:
        """Create a text summary of history items."""
        if not items:
            return "No prior history."

        # Extract key information
        agents_seen = set()
        decisions = []
        errors = []

        for item in items:
            if "agent" in item:
                agents_seen.add(item["agent"])
            if "reason" in item:
                decisions.append(item["reason"][:50])
            if "error" in str(item).lower():
                errors.append(str(item)[:50])

        summary_parts = [
            f"Processed {len(items)} steps.",
            f"Agents involved: {', '.join(agents_seen)}." if agents_seen else "",
            f"Key decisions: {len(decisions)}." if decisions else "",
            f"Errors encountered: {len(errors)}." if errors else ""
        ]

        return " ".join(p for p in summary_parts if p)


class MemorySystem:
    """
    Unified memory system combining all memory types.
    """

    def __init__(self, knowledge_base_path: str = "data/knowledge_base.json"):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.knowledge = KnowledgeBase(knowledge_base_path)

    def start_session(self, task: str, parameters: Dict[str, Any] = None):
        """Start a new working session."""
        self.working.clear()
        self.working.set_task(task, parameters)

    def record_outcome(
        self,
        agent: str,
        action: str,
        success: bool,
        context_summary: str = ""
    ):
        """Record an interaction outcome."""
        self.episodic.add_episode(
            agent=agent,
            action=action,
            outcome="success" if success else "failure",
            context_summary=context_summary
        )

    def get_context_summary(self, max_items: int = 10) -> Dict[str, Any]:
        """Get compressed context summary."""
        episodic_data = self.episodic.to_dict()
        compressed = ContextCompressor.compress(episodic_data, max_items)
        return {
            "working_memory": {
                "task": self.working.current_task,
                "parameters": self.working.active_parameters
            },
            "history": compressed,
            "knowledge_rules": self.knowledge.domain_rules
        }
