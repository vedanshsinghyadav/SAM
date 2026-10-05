"""
SAM Memory Engine Subsystem.
Provides persistent ACID-compliant SQLite storage and dual-tier semantic vector retrieval.
Part of Milestone 2: FEAT-MEM-001, FEAT-MEM-002.
"""

from src.sam.memory.interface import (
    IMemoryEngine,
    IMemoryStore,
    MemoryFact,
    MemorySearchResult,
    RetrievalQuery,
)
from src.sam.memory.store import SQLiteMemoryStore
from src.sam.memory.vector import (
    MemoryEngine,
    MemoryEngineAdapter,
    OfflineHeuristicScorer,
    VectorMemoryEngine,
    cosine_similarity,
    deserialize_embedding,
    serialize_embedding,
)

__all__ = [
    "IMemoryEngine",
    "IMemoryStore",
    "MemoryFact",
    "MemorySearchResult",
    "RetrievalQuery",
    "SQLiteMemoryStore",
    "MemoryEngine",
    "MemoryEngineAdapter",
    "VectorMemoryEngine",
    "OfflineHeuristicScorer",
    "cosine_similarity",
    "serialize_embedding",
    "deserialize_embedding",
]
