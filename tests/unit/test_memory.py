"""
Unit and Integration Test Suite for High-Level MemoryEngine & MemoryEngineAdapter.
Validates:
- Protocol compliance (IMemoryEngine)
- End-to-end memory engine lifecycle
- ACID restart durability across distinct engine instances
- Exact KV store operations (set, retrieve, overwrite, delete)
- Fuzzy semantic retrieval and domain-aware heuristic recall
- Score filtering (min_score=0.0, min_score=1.0, min_score=0.40 default)
- Boundary conditions (empty queries, SQL injection payloads, Unicode Hindi)
- Concurrency and thread safety
- Ephemeral temp dir cleanup on close
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
import pytest

from src.sam.memory import (
    IMemoryEngine,
    MemoryEngine,
    MemoryEngineAdapter,
    MemoryFact,
    MemorySearchResult,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db():
    """Provides a fresh isolated database path cleaned up on completion."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="sam_mem_e2e_")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            pass


@pytest.fixture
def engine(temp_db):
    """Provides an initialized MemoryEngine instance with Ollama disabled."""
    e = MemoryEngine(db_path=temp_db, enable_ollama=False)
    yield e
    e.close()


# ============================================================================
# 1. Protocol & Factory Compatibility
# ============================================================================

class TestEngineProtocolAndAdapter:
    def test_implements_imemory_engine_protocol(self, engine):
        assert isinstance(engine, IMemoryEngine)

    def test_adapter_alias_identical_to_memory_engine(self):
        assert MemoryEngineAdapter is MemoryEngine

    def test_ephemeral_db_cleanup_on_close(self):
        eng = MemoryEngine(enable_ollama=False)
        assert eng._temp_dir is not None
        assert os.path.exists(eng._temp_dir)
        temp_dir = eng._temp_dir
        eng.close()
        assert not os.path.exists(temp_dir)


# ============================================================================
# 2. Fact Storage & Retrieval Lifecycle
# ============================================================================

class TestEngineFactStorage:
    def test_store_fact_returns_positive_id(self, engine):
        fid = engine.store_fact("First stored fact", category="general")
        assert fid is not None
        assert fid > 0

    def test_get_fact_by_id(self, engine):
        fid = engine.store_fact(
            "Project SAM repo",
            category="dev",
            metadata={"path": "D:/Projects/SAM", "lang": "python"}
        )
        fact = engine.get_fact(fid)
        assert fact is not None
        assert fact.id == fid
        assert fact.content == "Project SAM repo"
        assert fact.category == "dev"
        assert fact.metadata["path"] == "D:/Projects/SAM"

    def test_list_facts_filtering(self, engine):
        engine.store_fact("Fact 1", category="study")
        engine.store_fact("Fact 2", category="dev")
        all_facts = engine.list_facts()
        assert len(all_facts) == 2
        dev_facts = engine.list_facts(category="dev")
        assert len(dev_facts) == 1
        assert dev_facts[0].content == "Fact 2"


# ============================================================================
# 3. Exact Key-Value Preferences
# ============================================================================

class TestEngineExactKV:
    def test_set_and_retrieve_exact(self, engine):
        engine.set_exact("editor", "VS Code")
        assert engine.retrieve_exact("editor") == "VS Code"

    def test_overwrite_exact(self, engine):
        engine.set_exact("theme", "light")
        engine.set_exact("theme", "dark")
        assert engine.retrieve_exact("theme") == "dark"

    def test_nonexistent_returns_none(self, engine):
        assert engine.retrieve_exact("unregistered_key") is None

    def test_delete_exact(self, engine):
        engine.set_exact("temp_pref", "val")
        assert engine.delete_exact("temp_pref") is True
        assert engine.retrieve_exact("temp_pref") is None


# ============================================================================
# 4. ACID Durability Across Process/Engine Restarts
# ============================================================================

class TestEnginePersistenceAcrossRestarts:
    def test_persists_across_restart(self, temp_db):
        m1 = MemoryEngine(db_path=temp_db, enable_ollama=False)
        fid = m1.store_fact("My COA notes are in D:/Notes/COA", category="study")
        m1.set_exact("notes_location", "D:/Notes/COA")
        m1.close()

        # Reopen with fresh instance
        m2 = MemoryEngine(db_path=temp_db, enable_ollama=False)
        try:
            assert m2.retrieve_exact("notes_location") == "D:/Notes/COA"
            fact = m2.get_fact(fid)
            assert fact is not None
            assert fact.content == "My COA notes are in D:/Notes/COA"

            # Fuzzy search on reopened engine
            results = m2.search_facts("COA notes")
            assert len(results) > 0
            assert "D:/Notes/COA" in results[0].fact.content
            assert results[0].similarity_score >= 0.40
        finally:
            m2.close()


# ============================================================================
# 5. Fuzzy Semantic Retrieval & Heuristic Recall
# ============================================================================

class TestEngineSemanticSearch:
    def test_fuzzy_query_project_folder(self, engine):
        engine.store_fact(
            "Primary project SAM source code is at D:/Projects/SAM",
            category="dev",
            metadata={"path": "D:/Projects/SAM"}
        )
        results = engine.search_facts("project folder")
        assert len(results) > 0
        assert results[0].similarity_score >= 0.40
        assert "D:/Projects/SAM" in results[0].fact.content

    def test_fuzzy_query_my_notes(self, engine):
        engine.store_fact("My COA notes are in D:/Notes/COA", category="study")
        results = engine.search_facts("where are my notes?")
        assert len(results) > 0
        assert results[0].similarity_score >= 0.40
        assert "D:/Notes/COA" in results[0].fact.content

    def test_ranks_most_similar_first(self, engine):
        engine.store_fact("Random groceries list", category="misc")
        engine.store_fact("COA lecture notes and exam study material in D:/Notes/COA", category="study")
        results = engine.search_facts("COA notes exam")
        assert len(results) > 0
        assert "COA" in results[0].fact.content
        assert results[0].similarity_score >= 0.70

    def test_filters_below_threshold(self, engine):
        engine.store_fact("My COA notes are in D:/Notes/COA", category="study")
        results = engine.search_facts("completely unrelated baking recipe for chocolate cake", min_score=0.40)
        assert len(results) == 0

    def test_top_k_truncation(self, engine):
        for i in range(10):
            engine.store_fact(f"Topic {i} notes for exam", category="study")
        results = engine.search_facts("exam notes", top_k=3)
        assert len(results) == 3
        # Assert non-ascending score order
        for i in range(len(results) - 1):
            assert results[i].similarity_score >= results[i + 1].similarity_score


# ============================================================================
# 6. Boundary Cases & Harness Anomaly Remediation
# ============================================================================

class TestEngineBoundaries:
    def test_empty_query_returns_empty_list(self, engine):
        engine.store_fact("Some stored fact")
        assert engine.search_facts("") == []
        assert engine.search_facts("   ") == []

    def test_single_character_query_safe(self, engine):
        engine.store_fact("Single character test fact")
        res = engine.search_facts("a")
        assert isinstance(res, list)

    def test_sql_injection_payload_containment(self, engine):
        payload = "Robert'); DROP TABLE facts;--"
        fid = engine.store_fact(payload, category="injection")
        assert fid > 0

        # Query for single token "Robert" must successfully retrieve the fact
        res = engine.search_facts("Robert", min_score=0.40)
        assert len(res) > 0
        assert res[0].fact.id == fid
        assert res[0].similarity_score >= 0.40

    def test_short_token_salient_keyword_editor(self, engine):
        engine.store_fact("User's primary editor is VS Code", category="pref")
        res = engine.search_facts("editor", min_score=0.40)
        assert len(res) > 0
        assert res[0].similarity_score >= 0.40

    def test_unicode_hindi_fuzzy_search(self, engine):
        engine.store_fact("COA के नोट्स यहाँ हैं: D:/Notes/COA", category="study")
        res = engine.search_facts("COA नोट्स", min_score=0.40)
        assert len(res) > 0
        assert res[0].similarity_score >= 0.40

    def test_min_score_boundary_zero(self, engine):
        engine.store_fact("Python language")
        engine.store_fact("Baking cookies")
        res = engine.search_facts("quantum physics", min_score=0.0)
        assert len(res) == 2

    def test_min_score_boundary_one(self, engine):
        engine.store_fact("exact match target string")
        engine.store_fact("partial match target string")
        res = engine.search_facts("exact match target string", min_score=1.0)
        assert len(res) == 1
        assert res[0].fact.content == "exact match target string"
        assert res[0].similarity_score == 1.0


# ============================================================================
# 7. Concurrency & Multi-Threaded Stress
# ============================================================================

class TestEngineConcurrency:
    def test_concurrent_search_and_store(self, engine):
        errors = []

        def writer():
            try:
                for i in range(15):
                    engine.store_fact(f"Dynamic concurrent fact {i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(15):
                    engine.search_facts("concurrent fact")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        w = threading.Thread(target=writer)
        r = threading.Thread(target=reader)

        w.start()
        r.start()

        w.join()
        r.join()

        assert len(errors) == 0
