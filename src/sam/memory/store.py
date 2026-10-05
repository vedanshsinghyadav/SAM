"""
SQLite Persistent Storage Engine for Project SAM.
Implements IMemoryStore protocol with ACID restart persistence, WAL mode,
thread-safe concurrency, SQL injection resilience, and defensive JSON handling.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from src.sam.common.config import get_config
from src.sam.memory.interface import IMemoryStore, MemoryFact

logger = logging.getLogger("sam.memory.store")


class SQLiteMemoryStore(IMemoryStore):
    """
    ACID-compliant SQLite persistent storage engine for SAM.
    Persists fact records and exact key-value preferences across restarts.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        timeout: float = 10.0,
        busy_timeout_ms: int = 5000
    ) -> None:
        """
        Initialize SQLite persistent memory store.

        Args:
            db_path: Filesystem path to SQLite database. If None, uses PathConfig default.
                     Supports ':memory:' for isolated ephemeral execution.
            timeout: Connection timeout in seconds.
            busy_timeout_ms: Milliseconds SQLite engine waits for locks before raising.
        """
        if db_path is None:
            self.db_path = get_config().paths.memory_db_path
        else:
            self.db_path = str(db_path)

        self.timeout = timeout
        self.busy_timeout_ms = busy_timeout_ms
        self._lock = threading.RLock()
        self._is_closed = False
        self._is_in_memory = (self.db_path == ":memory:")
        self._persistent_conn: Optional[sqlite3.Connection] = None

        if self._is_in_memory:
            # Maintain persistent connection for :memory: database so state survives queries
            self._persistent_conn = sqlite3.connect(":memory:", timeout=self.timeout, check_same_thread=False)
            self._persistent_conn.row_factory = sqlite3.Row
        else:
            # Create directory tree if not exists
            parent = os.path.dirname(os.path.abspath(self.db_path))
            if parent:
                os.makedirs(parent, exist_ok=True)

        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Thread-safe context manager providing an active SQLite connection.
        Ensures proper pragmas and cleans up connection on exit to prevent
        Windows file locking conflicts.
        """
        with self._lock:
            if self._is_closed:
                raise RuntimeError("SQLiteMemoryStore is closed.")

            if self._is_in_memory:
                if self._persistent_conn is None:
                    raise RuntimeError("Persistent in-memory connection is closed.")
                yield self._persistent_conn
            else:
                conn = sqlite3.connect(self.db_path, timeout=self.timeout)
                conn.row_factory = sqlite3.Row
                try:
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA synchronous = NORMAL;")
                    conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
                    conn.execute("PRAGMA foreign_keys = ON;")
                    yield conn
                finally:
                    conn.close()

    def _init_schema(self) -> None:
        """Initialize tables and indices with idempotent DDL statements."""
        with self._connect() as conn:
            cur = conn.cursor()
            # Facts table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    embedding BLOB,
                    timestamp REAL NOT NULL
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_timestamp ON facts(timestamp);")

            # Key-Value store table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
            """)
            conn.commit()

    # ========================================================================
    # Fact Storage & Retrieval (CRUD)
    # ========================================================================

    def store_fact(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[bytes] = None
    ) -> int:
        """
        Persist a fact in the database.

        Args:
            content: Raw textual statement or fact.
            category: Domain classification tag.
            metadata: Optional dictionary of metadata attributes.
            embedding: Optional binary float blob.

        Returns:
            int: Auto-generated primary key ID (> 0).
        """
        safe_meta = json.dumps(metadata if metadata is not None else {})
        now = time.time()
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO facts (content, category, metadata, embedding, timestamp) VALUES (?, ?, ?, ?, ?)",
                (content, category or "general", safe_meta, embedding, now)
            )
            fact_id = cur.lastrowid
            conn.commit()
            if fact_id is None:
                raise RuntimeError("Failed to obtain lastrowid after inserting fact.")
            return int(fact_id)

    def get_fact(self, fact_id: int) -> Optional[MemoryFact]:
        """Retrieve a specific fact by its primary key ID."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, content, category, metadata, timestamp FROM facts WHERE id = ?",
                (fact_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_fact(row)

    def get_fact_with_embedding(self, fact_id: int) -> Tuple[Optional[MemoryFact], Optional[bytes]]:
        """Retrieve a specific fact and its raw embedding blob."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, content, category, metadata, timestamp, embedding FROM facts WHERE id = ?",
                (fact_id,)
            )
            row = cur.fetchone()
            if not row:
                return None, None
            fact = self._row_to_fact(row)
            emb = row["embedding"] if "embedding" in row.keys() else row[5]
            return fact, bytes(emb) if emb is not None else None

    def list_facts(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[MemoryFact]:
        """
        List facts, optionally filtered by category and paginated.

        Args:
            category: If provided, filter exclusively by this category.
            limit: Maximum number of records to return.
            offset: Number of records to skip.
        """
        query = "SELECT id, content, category, metadata, timestamp FROM facts"
        params: List[Any] = []

        if category is not None:
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [self._row_to_fact(row) for row in rows]

    def list_facts_with_embeddings(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Tuple[MemoryFact, Optional[bytes]]]:
        """List facts along with their binary embeddings."""
        query = "SELECT id, content, category, metadata, timestamp, embedding FROM facts"
        params: List[Any] = []

        if category is not None:
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY id ASC"

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            results = []
            for row in rows:
                fact = self._row_to_fact(row)
                emb = row["embedding"] if "embedding" in row.keys() else row[5]
                results.append((fact, bytes(emb) if emb is not None else None))
            return results

    def count_facts(self, category: Optional[str] = None) -> int:
        """Count total facts, optionally filtered by category."""
        query = "SELECT COUNT(*) FROM facts"
        params: List[Any] = []
        if category is not None:
            query += " WHERE category = ?"
            params.append(category)

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def update_fact(
        self,
        fact_id: int,
        content: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[bytes] = None
    ) -> bool:
        """
        Update fields of an existing fact.

        Returns:
            bool: True if row existed and was updated; False otherwise.
        """
        updates: List[str] = []
        params: List[Any] = []

        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        if embedding is not None:
            updates.append("embedding = ?")
            params.append(embedding)

        if not updates:
            return False

        params.append(fact_id)
        query = f"UPDATE facts SET {', '.join(updates)} WHERE id = ?"

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(query, tuple(params))
            conn.commit()
            return cur.rowcount > 0

    def delete_fact(self, fact_id: int) -> bool:
        """Delete fact by ID. Returns True if deleted, False otherwise."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
            conn.commit()
            return cur.rowcount > 0

    # ========================================================================
    # Key-Value Store Operations
    # ========================================================================

    def set_exact(self, key: str, value: str) -> None:
        """
        Store or overwrite an exact string preference by key.

        Args:
            key: Unique key identifier.
            value: String value to store.
        """
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string.")

        now = time.time()
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO kv_store (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, str(value), now)
            )
            conn.commit()

    def retrieve_exact(self, key: str) -> Optional[str]:
        """
        Retrieve exact string preference by key.

        Returns:
            str or None: Stored value if key exists, otherwise None.
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
            row = cur.fetchone()
            return str(row[0]) if row else None

    def delete_exact(self, key: str) -> bool:
        """Delete exact preference by key. Returns True if deleted."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            conn.commit()
            return cur.rowcount > 0

    def list_exact_keys(self) -> List[str]:
        """Return sorted list of all keys currently in the KV store."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT key FROM kv_store ORDER BY key ASC")
            rows = cur.fetchall()
            return [str(row[0]) for row in rows]

    # ========================================================================
    # Maintenance, Cleanup & Lifecycle
    # ========================================================================

    def clear_all(self) -> None:
        """Purge all records from both facts and kv_store tables."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM facts;")
            cur.execute("DELETE FROM kv_store;")
            conn.commit()

    def close(self) -> None:
        """Close store, checkpoint WAL, and release all file locks."""
        with self._lock:
            if self._is_closed:
                return

            if self._is_in_memory:
                if self._persistent_conn:
                    self._persistent_conn.close()
                    self._persistent_conn = None
            else:
                # Run checkpoint on file-backed database before closing
                try:
                    conn = sqlite3.connect(self.db_path, timeout=self.timeout)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    conn.close()
                except Exception as ex:
                    logger.debug("WAL checkpoint on close suppressed: %s", ex)

            self._is_closed = True

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ========================================================================
    # Private Helpers
    # ========================================================================

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> MemoryFact:
        """Defensively deserialize a database row into a MemoryFact model."""
        meta_raw = row["metadata"] if "metadata" in row.keys() else row[3]
        meta: Dict[str, Any] = {}
        if meta_raw:
            try:
                parsed = json.loads(meta_raw)
                if isinstance(parsed, dict):
                    meta = parsed
                else:
                    meta = {"value": parsed}
            except Exception:
                meta = {}

        return MemoryFact(
            id=int(row["id"] if "id" in row.keys() else row[0]),
            content=str(row["content"] if "content" in row.keys() else row[1]),
            category=str(row["category"] if "category" in row.keys() else row[2]),
            metadata=meta,
            timestamp=float(row["timestamp"] if "timestamp" in row.keys() else row[4])
        )
