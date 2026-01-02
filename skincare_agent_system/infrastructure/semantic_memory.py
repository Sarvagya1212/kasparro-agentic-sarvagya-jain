"""
Semantic Memory: Vector-based memory for experience retrieval.
Uses ChromaDB for local vector storage and similarity search.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SemanticMemory")


@dataclass
class MemoryEntry:
    """A single memory entry with embedding."""
    memory_id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent: str = "unknown"
    memory_type: str = "experience"  # experience, fact, decision
    importance: float = 0.5  # 0-1, for pruning
    access_count: int = 0


@dataclass
class MemorySearchResult:
    """Result from semantic search."""
    memory: MemoryEntry
    similarity: float
    rank: int


class EmbeddingProvider:
    """
    Abstract embedding provider.
    Subclass for different embedding backends.
    """

    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        raise NotImplementedError

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(t) for t in texts]


class SimpleHashEmbedding(EmbeddingProvider):
    """
    Simple hash-based pseudo-embedding for testing.
    Not suitable for production - use LLM embeddings.
    """

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, text: str) -> List[float]:
        """Create pseudo-embedding from text hash."""
        # Hash text and expand to embedding dimensions
        h = hashlib.sha256(text.encode()).hexdigest()

        # Convert hex to floats
        embedding = []
        for i in range(0, min(len(h), self.dimensions * 2), 2):
            val = int(h[i:i+2], 16) / 255.0 - 0.5
            embedding.append(val)

        # Pad if needed
        while len(embedding) < self.dimensions:
            embedding.append(0.0)

        return embedding[:self.dimensions]


class LLMEmbedding(EmbeddingProvider):
    """LLM-based embedding using Mistral or OpenAI."""

    def __init__(self, model: str = "mistral-embed"):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from skincare_agent_system.infrastructure.llm_client import LLMClient
                self._client = LLMClient()
            except Exception as e:
                logger.warning(f"Could not initialize LLM client: {e}")
        return self._client

    def embed(self, text: str) -> List[float]:
        """Generate embedding using LLM."""
        client = self._get_client()
        if client and hasattr(client, 'embed'):
            return client.embed(text)

        # Fallback to hash embedding
        return SimpleHashEmbedding().embed(text)


class InMemoryVectorStore:
    """
    Simple in-memory vector store.
    Use ChromaDB for production.
    """

    def __init__(self):
        self._memories: Dict[str, MemoryEntry] = {}

    def add(self, memory: MemoryEntry) -> None:
        self._memories[memory.memory_id] = memory

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        return self._memories.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filter_fn: Optional[Callable[[MemoryEntry], bool]] = None
    ) -> List[MemorySearchResult]:
        """Search by cosine similarity."""
        results = []

        for memory in self._memories.values():
            if filter_fn and not filter_fn(memory):
                continue

            if memory.embedding:
                similarity = self._cosine_similarity(query_embedding, memory.embedding)
                results.append((memory, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)

        return [
            MemorySearchResult(memory=m, similarity=s, rank=i)
            for i, (m, s) in enumerate(results[:limit])
        ]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity."""
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def count(self) -> int:
        return len(self._memories)

    def all(self) -> List[MemoryEntry]:
        return list(self._memories.values())


class ChromaDBStore:
    """
    ChromaDB-backed vector store.
    Requires: pip install chromadb
    """

    def __init__(self, collection_name: str = "agent_memories"):
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialized = False

    def _initialize(self) -> bool:
        """Lazy initialize ChromaDB."""
        if self._initialized:
            return self._collection is not None

        try:
            import chromadb
            self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._initialized = True
            logger.info(f"ChromaDB collection '{self.collection_name}' initialized")
            return True
        except ImportError:
            logger.warning("ChromaDB not installed. Using in-memory store.")
            self._initialized = True
            return False
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
            self._initialized = True
            return False

    def add(self, memory: MemoryEntry) -> None:
        if not self._initialize() or not self._collection:
            return

        self._collection.add(
            ids=[memory.memory_id],
            embeddings=[memory.embedding] if memory.embedding else None,
            documents=[memory.content],
            metadatas=[{
                "agent": memory.agent,
                "type": memory.memory_type,
                "importance": memory.importance,
                "timestamp": memory.timestamp
            }]
        )

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        if not self._initialize() or not self._collection:
            return None

        result = self._collection.get(ids=[memory_id])
        if result and result['documents']:
            return MemoryEntry(
                memory_id=memory_id,
                content=result['documents'][0],
                embedding=result['embeddings'][0] if result.get('embeddings') else None,
                metadata=result['metadatas'][0] if result.get('metadatas') else {}
            )
        return None

    def delete(self, memory_id: str) -> bool:
        if not self._initialize() or not self._collection:
            return False

        try:
            self._collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False

    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filter_fn: Optional[Callable[[MemoryEntry], bool]] = None
    ) -> List[MemorySearchResult]:
        if not self._initialize() or not self._collection:
            return []

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )

        search_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                memory = MemoryEntry(
                    memory_id=memory_id,
                    content=results['documents'][0][i] if results.get('documents') else "",
                    metadata=results['metadatas'][0][i] if results.get('metadatas') else {},
                    embedding=results['embeddings'][0][i] if results.get('embeddings') else None
                )

                if filter_fn and not filter_fn(memory):
                    continue

                distance = results['distances'][0][i] if results.get('distances') else 0
                similarity = 1 - distance  # Convert distance to similarity

                search_results.append(MemorySearchResult(
                    memory=memory,
                    similarity=similarity,
                    rank=len(search_results)
                ))

        return search_results

    def count(self) -> int:
        if not self._initialize() or not self._collection:
            return 0
        return self._collection.count()


class SemanticMemory:
    """
    Semantic memory system for agents.

    Features:
    - Store experiences with embeddings
    - Similarity-based retrieval
    - Memory consolidation and pruning
    - Agent-specific memory filtering
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        use_chromadb: bool = False,
        max_memories: int = 10000
    ):
        self._embedding = embedding_provider or SimpleHashEmbedding()
        self._max_memories = max_memories

        if use_chromadb:
            self._store = ChromaDBStore()
        else:
            self._store = InMemoryVectorStore()

    def store(
        self,
        content: str,
        agent: str,
        memory_type: str = "experience",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """
        Store a new memory with embedding.
        """
        # Generate ID
        memory_id = f"mem_{agent}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Generate embedding
        embedding = self._embedding.embed(content)

        memory = MemoryEntry(
            memory_id=memory_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            agent=agent,
            memory_type=memory_type,
            importance=importance
        )

        self._store.add(memory)
        logger.debug(f"Stored memory {memory_id} for agent {agent}")

        # Prune if needed
        if isinstance(self._store, InMemoryVectorStore):
            if self._store.count() > self._max_memories:
                self._prune()

        return memory

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        agent: Optional[str] = None,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0
    ) -> List[MemorySearchResult]:
        """
        Retrieve relevant memories using semantic search.
        """
        # Generate query embedding
        query_embedding = self._embedding.embed(query)

        # Create filter
        def filter_fn(memory: MemoryEntry) -> bool:
            if agent and memory.agent != agent:
                return False
            if memory_type and memory.memory_type != memory_type:
                return False
            if memory.importance < min_importance:
                return False
            return True

        results = self._store.search(query_embedding, limit * 2, filter_fn)

        # Update access counts
        for result in results[:limit]:
            result.memory.access_count += 1

        return results[:limit]

    def get_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID."""
        return self._store.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        return self._store.delete(memory_id)

    def consolidate(self, agent: str) -> int:
        """
        Consolidate memories for an agent.
        Merge similar memories and increase importance.
        """
        if not isinstance(self._store, InMemoryVectorStore):
            return 0

        memories = [m for m in self._store.all() if m.agent == agent]
        consolidated = 0

        # Group similar memories
        for i, mem1 in enumerate(memories):
            if not mem1.embedding:
                continue

            for mem2 in memories[i+1:]:
                if not mem2.embedding:
                    continue

                similarity = self._store._cosine_similarity(
                    mem1.embedding, mem2.embedding
                )

                if similarity > 0.9:
                    # Merge: keep higher importance, delete duplicate
                    if mem1.importance >= mem2.importance:
                        mem1.importance = min(1.0, mem1.importance + 0.1)
                        self._store.delete(mem2.memory_id)
                    else:
                        mem2.importance = min(1.0, mem2.importance + 0.1)
                        self._store.delete(mem1.memory_id)
                    consolidated += 1

        logger.info(f"Consolidated {consolidated} memories for {agent}")
        return consolidated

    def _prune(self) -> int:
        """
        Prune low-importance, rarely-accessed memories.
        """
        if not isinstance(self._store, InMemoryVectorStore):
            return 0

        memories = self._store.all()
        target = self._max_memories // 2

        # Score memories for pruning
        scored = [
            (m, m.importance * 0.5 + min(m.access_count / 10, 0.5))
            for m in memories
        ]
        scored.sort(key=lambda x: x[1])

        pruned = 0
        for memory, score in scored:
            if len(memories) - pruned <= target:
                break
            self._store.delete(memory.memory_id)
            pruned += 1

        logger.info(f"Pruned {pruned} low-importance memories")
        return pruned

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        count = self._store.count() if hasattr(self._store, 'count') else 0
        return {
            "total_memories": count,
            "max_memories": self._max_memories,
            "embedding_type": type(self._embedding).__name__,
            "store_type": type(self._store).__name__
        }


# Singleton instance
_semantic_memory: Optional[SemanticMemory] = None


def get_semantic_memory(use_chromadb: bool = False) -> SemanticMemory:
    """Get or create semantic memory singleton."""
    global _semantic_memory

    if _semantic_memory is None:
        _semantic_memory = SemanticMemory(use_chromadb=use_chromadb)

    return _semantic_memory


def reset_semantic_memory() -> None:
    """Reset semantic memory singleton (for testing)."""
    global _semantic_memory
    _semantic_memory = None
