"""
Unit Test Suite for SAM SQLite Persistent Memory Store.
Validates:
- Protocol compliance (IMemoryStore)
- Schema initialization and Pragmas (WAL mode, busy_timeout)
- Facts CRUD and auto-increment monotonicity
- Exact KV preferences set and retrieve
- ACID persistence across process and engine reboots
- Thread safety and multi-worker concurrent operations
- SQL injection immunity and payload isolation
- Defensive JSON metadata recovery
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import tempfile
import threading
import time
from typing import List
import pytest

from src.sam.memory.interface import IMemoryStore, MemoryFact
from src.sam.memory.store import SQLiteMemoryStore


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Provides a fresh isolated temporary database path cleaned up on exit."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="sam_unit_mem_")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            pass


@pytest.fixture
def store(temp_db_path):
    """Provides an initialized SQLiteMemoryStore instance."""
    s = SQLiteMemoryStore(db_path=temp_db_path)
    yield s
    s.close()


# ============================================================================
# 1. Lifecycle and Pragmas
# ============================================================================

class TestStoreLifecycle:
    def test_implements_protocol(self, store):
        assert isinstance(store, IMemoryStore)

    def test_custom_path_creates_parent_directories(self, tmp_path):
        nested_path = tmp_path / "deeply" / "nested" / "dir" / "memory.db"
        s = SQLiteMemoryStore(db_path=nested_path)
        try:
            assert os.path.exists(nested_path)
            fid = s.store_fact("Test directory creation")
            assert fid > 0
        finally:
            s.close()

    def test_in_memory_mode(self):
        s = SQLiteMemoryStore(db_path=":memory:")
        try:
            fid = s.store_fact("Fact in memory")
            assert fid > 0
            retrieved = s.get_fact(fid)
            assert retrieved is not None
            assert retrieved.content == "Fact in memory"
        finally:
            s.close()

    def test_wal_pragma_applied(self, temp_db_path):
        s = SQLiteMemoryStore(db_path=temp_db_path)
        try:
            with s._connect() as conn:
                row = conn.execute("PRAGMA journal_mode;").fetchone()
                assert row[0].lower() == "wal"
        finally:
            s.close()

    def test_closed_store_raises_runtime_error(self, temp_db_path):
        s = SQLiteMemoryStore(db_path=temp_db_path)
        s.close()
        with pytest.raises(RuntimeError, match="closed"):
            s.store_fact("Should fail")

    def test_context_manager_usage(self, temp_db_path):
        with SQLiteMemoryStore(db_path=temp_db_path) as s:
            fid = s.store_fact("Context managed fact")
            assert fid > 0
        assert s._is_closed is True


# ============================================================================
# 2. Facts CRUD Operations
# ============================================================================

class TestFactsCRUD:
    def test_store_fact_returns_positive_id(self, store):
        fid = store.store_fact("First knowledge fact", category="general")
        assert fid > 0

    def test_store_fact_id_autoincrement(self, store):
        id1 = store.store_fact("Fact 1")
        id2 = store.store_fact("Fact 2")
        id3 = store.store_fact("Fact 3")
        assert id2 > id1
        assert id3 > id2

    def test_get_fact_success(self, store):
        fid = store.store_fact("My COA notes are in D:/Notes/COA", category="study", metadata={"source": "user"})
        fact = store.get_fact(fid)
        assert fact is not None
        assert fact.id == fid
        assert fact.content == "My COA notes are in D:/Notes/COA"
        assert fact.category == "study"
        assert fact.metadata == {"source": "user"}
        assert fact.timestamp > 0

    def test_get_fact_nonexistent_returns_none(self, store):
        assert store.get_fact(999999) is None

    def test_list_facts_all(self, store):
        store.store_fact("Fact A", category="study")
        store.store_fact("Fact B", category="dev")
        facts = store.list_facts()
        assert len(facts) == 2
        assert facts[0].content == "Fact A"
        assert facts[1].content == "Fact B"

    def test_list_facts_category_filter(self, store):
        store.store_fact("Study fact", category="study")
        store.store_fact("Dev fact", category="dev")
        study_facts = store.list_facts(category="study")
        assert len(study_facts) == 1
        assert study_facts[0].content == "Study fact"

    def test_list_facts_pagination(self, store):
        for i in range(5):
            store.store_fact(f"Item {i}")
        page1 = store.list_facts(limit=2, offset=0)
        assert len(page1) == 2
        assert page1[0].content == "Item 0"
        page2 = store.list_facts(limit=2, offset=2)
        assert len(page2) == 2
        assert page2[0].content == "Item 2"

    def test_count_facts(self, store):
        assert store.count_facts() == 0
        store.store_fact("Fact 1", category="general")
        store.store_fact("Fact 2", category="study")
        assert store.count_facts() == 2
        assert store.count_facts(category="study") == 1
        assert store.count_facts(category="dev") == 0

    def test_update_fact_content_and_metadata(self, store):
        fid = store.store_fact("Old text", category="general")
        success = store.update_fact(fid, content="New text", metadata={"updated": True})
        assert success is True
        updated = store.get_fact(fid)
        assert updated is not None
        assert updated.content == "New text"
        assert updated.metadata == {"updated": True}

    def test_update_fact_nonexistent(self, store):
        assert store.update_fact(99999, content="Noop") is False

    def test_delete_fact_success(self, store):
        fid = store.store_fact("To be deleted")
        assert store.delete_fact(fid) is True
        assert store.get_fact(fid) is None
        assert store.count_facts() == 0

    def test_delete_fact_nonexistent(self, store):
        assert store.delete_fact(99999) is False


# ============================================================================
# 3. Metadata Serialization
# ============================================================================

class TestMetadataSerialization:
    def test_metadata_empty_dict(self, store):
        fid = store.store_fact("Fact with empty metadata", metadata={})
        fact = store.get_fact(fid)
        assert fact.metadata == {}

    def test_metadata_complex_nested_structure(self, store):
        meta = {
            "tags": ["python", "sam", "windows"],
            "nested": {"score": 98.5, "verified": True},
            "owner": None
        }
        fid = store.store_fact("Fact with complex metadata", metadata=meta)
        fact = store.get_fact(fid)
        assert fact.metadata["tags"] == ["python", "sam", "windows"]
        assert fact.metadata["nested"]["score"] == 98.5
        assert fact.metadata["nested"]["verified"] is True

    def test_defensive_recovery_corrupted_json(self, temp_db_path):
        s = SQLiteMemoryStore(db_path=temp_db_path)
        try:
            with s._connect() as conn:
                conn.execute(
                    "INSERT INTO facts (content, category, metadata, timestamp) VALUES (?, ?, ?, ?)",
                    ("Fact with broken json", "general", "{corrupted_json", time.time())
                )
                conn.commit()
            facts = s.list_facts()
            assert len(facts) == 1
            assert facts[0].metadata == {}
        finally:
            s.close()


# ============================================================================
# 4. Exact Key-Value Store
# ============================================================================

class TestExactKVStore:
    def test_set_and_retrieve_exact(self, store):
        store.set_exact("notes_dir", "D:/Notes/COA")
        assert store.retrieve_exact("notes_dir") == "D:/Notes/COA"

    def test_overwrite_existing_key(self, store):
        store.set_exact("active_project", "OldProject")
        store.set_exact("active_project", "NewProject")
        assert store.retrieve_exact("active_project") == "NewProject"

    def test_retrieve_nonexistent_returns_none(self, store):
        assert store.retrieve_exact("missing_key") is None

    def test_delete_exact(self, store):
        store.set_exact("temp_key", "value")
        assert store.delete_exact("temp_key") is True
        assert store.retrieve_exact("temp_key") is None
        assert store.delete_exact("temp_key") is False

    def test_list_exact_keys(self, store):
        store.set_exact("k2", "v2")
        store.set_exact("k1", "v1")
        store.set_exact("k3", "v3")
        keys = store.list_exact_keys()
        assert keys == ["k1", "k2", "k3"]

    def test_set_exact_invalid_key_raises(self, store):
        with pytest.raises(ValueError):
            store.set_exact("", "value")


# ============================================================================
# 5. ACID Durability Across Engine Restarts
# ============================================================================

class TestACIDPersistence:
    def test_state_persists_across_instances(self, temp_db_path):
        s1 = SQLiteMemoryStore(db_path=temp_db_path)
        fid1 = s1.store_fact("Fact created in instance 1", category="study")
        s1.set_exact("pref_lang", "Python")
        s1.close()

        # Reopen with fresh instance
        s2 = SQLiteMemoryStore(db_path=temp_db_path)
        try:
            fact = s2.get_fact(fid1)
            assert fact is not None
            assert fact.content == "Fact created in instance 1"
            assert s2.retrieve_exact("pref_lang") == "Python"
        finally:
            s2.close()

    def test_clean_file_removal_on_close(self, temp_db_path):
        s = SQLiteMemoryStore(db_path=temp_db_path)
        s.store_fact("Fact before remove")
        s.close()
        # On Windows, closing must release file locks so os.remove succeeds
        os.remove(temp_db_path)
        assert not os.path.exists(temp_db_path)


# ============================================================================
# 6. Security & SQL Injection Resilience
# ============================================================================

class TestSQLInjectionResilience:
    def test_sql_injection_payload_in_content(self, store):
        payload = "Robert'); DROP TABLE facts;--"
        fid = store.store_fact(payload, category="injection")
        assert fid > 0
        fact = store.get_fact(fid)
        assert fact is not None
        assert fact.content == payload
        # Table must still be intact
        assert store.count_facts() == 1

    def test_sql_injection_in_category(self, store):
        payload = "' OR 1=1; --"
        fid = store.store_fact("Some content", category=payload)
        assert fid > 0
        facts = store.list_facts(category=payload)
        assert len(facts) == 1
        assert facts[0].category == payload

    def test_sql_injection_in_kv_store(self, store):
        payload_key = "key'; DROP TABLE kv_store;--"
        payload_val = "val' OR '1'='1"
        store.set_exact(payload_key, payload_val)
        retrieved = store.retrieve_exact(payload_key)
        assert retrieved == payload_val


# ============================================================================
# 7. Concurrency & Thread Safety
# ============================================================================

class TestConcurrencyAndThreadSafety:
    def test_concurrent_fact_writes(self, store):
        def worker(start_num: int):
            for i in range(10):
                store.store_fact(f"Thread fact {start_num}-{i}")

        threads = []
        for t in range(5):
            th = threading.Thread(target=worker, args=(t,))
            threads.append(th)
            th.start()

        for th in threads:
            th.join()

        assert store.count_facts() == 50

    def test_concurrent_reads_and_writes(self, store):
        errors: List[Exception] = []

        def writer():
            try:
                for i in range(20):
                    store.store_fact(f"Concurrent fact {i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    store.list_facts()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        w_thread = threading.Thread(target=writer)
        r_thread = threading.Thread(target=reader)

        w_thread.start()
        r_thread.start()

        w_thread.join()
        r_thread.join()

        assert len(errors) == 0


# ============================================================================
# 8. Boundary Cases
# ============================================================================

class TestStoreBoundaries:
    def test_empty_content_string(self, store):
        fid = store.store_fact("", category="empty")
        assert fid > 0
        fact = store.get_fact(fid)
        assert fact.content == ""

    def test_large_content_payload(self, store):
        large_content = "X" * 200_000  # 200 KB
        fid = store.store_fact(large_content, category="large")
        fact = store.get_fact(fid)
        assert fact is not None
        assert len(fact.content) == 200_000

    def test_unicode_hindi_and_emojis(self, store):
        unicode_text = "COA के नोट्स यहाँ हैं: D:/Notes/COA 🚀 📚"
        fid = store.store_fact(unicode_text, category="hindi")
        fact = store.get_fact(fid)
        assert fact.content == unicode_text

    def test_clear_all_purges_everything(self, store):
        store.store_fact("Fact 1")
        store.set_exact("key1", "val1")
        store.clear_all()
        assert store.count_facts() == 0
        assert store.retrieve_exact("key1") is None
