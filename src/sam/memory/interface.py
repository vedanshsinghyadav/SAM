"""
Interface contracts and protocols for SAM Persistent Memory Subsystem.
Strictly conforms to PROJECT.md lines 180-208 and E2E Harness contracts.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import Field

from src.sam.common.types import CompatibleBaseModel


# ============================================================================
# Core Data Models
# ============================================================================

class MemoryFact(CompatibleBaseModel):
    """
    Structured record representing a discrete piece of knowledge stored in SAM.
    Persists user preferences, directory locations, environment facts, and study notes.
    """
    id: Optional[int] = Field(default=None, description="Unique primary key identifier in persistent store")
    content: str = Field(..., description="Raw textual knowledge or statement")
    category: str = Field(default="general", description="Logical categorization tag (e.g. 'study', 'dev', 'pref')")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary JSON-serializable structured attributes")
    timestamp: float = Field(default_factory=time.time, description="Unix epoch timestamp when fact was recorded")

    def summary(self) -> str:
        """Compact string representation for debugging and prompts."""
        return f"[{self.category}] (#{self.id or 'new'}) {self.content}"


class MemorySearchResult(CompatibleBaseModel):
    """
    Result container pairing a retrieved MemoryFact with its similarity relevance score.
    """
    fact: MemoryFact = Field(..., description="The stored fact matched by semantic retrieval")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Normalized similarity score in range [0.0, 1.0]")


class RetrievalQuery(CompatibleBaseModel):
    """
    Typed query specification for memory search requests.
    """
    query: str = Field(..., min_length=0, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, description="Maximum number of candidate facts to return")
    min_score: float = Field(default=0.4, ge=0.0, le=1.0, description="Minimum similarity score threshold")
    category: Optional[str] = Field(default=None, description="Optional category filter constraint")
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None, description="Optional key-value metadata filter")


# ============================================================================
# Protocol Definitions
# ============================================================================

@runtime_checkable
class IMemoryStore(Protocol):
    """
    Protocol for low-level persistent storage engines (e.g., SQLiteMemoryStore).
    Handles ACID CRUD for facts and key-value preference pairs.
    """

    def store_fact(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[bytes] = None
    ) -> int:
        """Persist a single fact record and return its unique positive integer ID."""
        ...

    def get_fact(self, fact_id: int) -> Optional[MemoryFact]:
        """Retrieve a specific fact by ID, returning None if nonexistent."""
        ...

    def list_facts(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[MemoryFact]:
        """List stored facts, optionally filtered by category and paginated."""
        ...

    def count_facts(self, category: Optional[str] = None) -> int:
        """Count stored facts, optionally filtered by category."""
        ...

    def update_fact(
        self,
        fact_id: int,
        content: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[bytes] = None
    ) -> bool:
        """Update an existing fact's fields. Returns True if row was updated."""
        ...

    def delete_fact(self, fact_id: int) -> bool:
        """Delete fact by ID. Returns True if row was deleted, False otherwise."""
        ...

    def set_exact(self, key: str, value: str) -> None:
        """Persist or update an exact key-value string preference."""
        ...

    def retrieve_exact(self, key: str) -> Optional[str]:
        """Retrieve exact string preference by key, returning None if not found."""
        ...

    def delete_exact(self, key: str) -> bool:
        """Delete exact preference by key. Returns True if deleted, False otherwise."""
        ...

    def list_exact_keys(self) -> List[str]:
        """Return sorted list of all registered keys in the exact KV store."""
        ...

    def clear_all(self) -> None:
        """Purge all stored facts and KV preferences (useful for test isolation)."""
        ...

    def close(self) -> None:
        """Close database connections and release file locks."""
        ...


@runtime_checkable
class IMemoryEngine(Protocol):
    """
    Protocol for high-level Long-Term Memory Engine as specified in PROJECT.md line 196.
    Unifies persistent storage with vector semantic search.
    """

    def store_fact(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Store fact with persistent vector embedding."""
        ...

    def search_facts(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.4
    ) -> List[MemorySearchResult]:
        """Perform fuzzy semantic search over stored facts."""
        ...

    def set_exact(self, key: str, value: str) -> None:
        """Set exact key-value preference."""
        ...

    def retrieve_exact(self, key: str) -> Optional[str]:
        """Retrieve exact key-value preference."""
        ...

    def close(self) -> None:
        """Close storage and vector engine resources."""
        ...
