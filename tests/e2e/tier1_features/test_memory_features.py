"""
Tier 1: Feature Coverage Tests for Long-Term Memory Engine (R3).
Covers:
- FEAT-MEM-001: Persistent Knowledge Store (5 tests)
- FEAT-MEM-002: Semantic Vector Retrieval (5 tests)
Total: 10 tests.
"""

import os
import tempfile
import pytest
from tests.e2e.harness import MemoryEngineAdapter


# ---------------------------------------------------------------------------
# FEAT-MEM-001: Persistent Knowledge Store
# ---------------------------------------------------------------------------

def test_feat_mem_001_stores_fact_and_returns_id():
    mem = MemoryEngineAdapter()
    try:
        fact_id = mem.store_fact("My COA notes are in D:/Notes/COA", category="notes")
        assert fact_id is not None
        assert fact_id > 0
    finally:
        mem.close()


def test_feat_mem_001_persists_across_engine_restart():
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="sam_test_restart_")
    os.close(fd)
    try:
        mem1 = MemoryEngineAdapter(db_path=db_path)
        mem1.store_fact("My COA notes are in D:/Notes/COA", category="study")
        mem1.set_exact("notes_location", "D:/Notes/COA")

        # Simulate process termination and restart
        mem2 = MemoryEngineAdapter(db_path=db_path)
        exact_val = mem2.retrieve_exact("notes_location")
        assert exact_val == "D:/Notes/COA"
        results = mem2.search_facts("COA notes")
        assert len(results) > 0
        assert "D:/Notes/COA" in results[0].fact.content
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_feat_mem_001_stores_metadata():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("Project SAM repo", category="dev", metadata={"path": "D:/Projects/SAM", "lang": "python"})
        res = mem.search_facts("Project SAM repo")
        assert len(res) > 0
        assert res[0].fact.metadata.get("path") == "D:/Projects/SAM"
    finally:
        mem.close()


def test_feat_mem_001_exact_kv_store_and_retrieve():
    mem = MemoryEngineAdapter()
    try:
        mem.set_exact("favorite_browser", "Chrome")
        assert mem.retrieve_exact("favorite_browser") == "Chrome"
        assert mem.retrieve_exact("non_existent_key") is None
    finally:
        mem.close()


def test_feat_mem_001_updates_existing_key():
    mem = MemoryEngineAdapter()
    try:
        mem.set_exact("coa_notes", "D:/Notes/Old")
        mem.set_exact("coa_notes", "D:/Notes/COA")
        assert mem.retrieve_exact("coa_notes") == "D:/Notes/COA"
    finally:
        mem.close()


# ---------------------------------------------------------------------------
# FEAT-MEM-002: Semantic Vector Retrieval
# ---------------------------------------------------------------------------

def test_feat_mem_002_fuzzy_query_project_folder():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("Primary project SAM source code is at D:/Projects/SAM", category="dev")
        results = mem.search_facts("project folder")
        assert len(results) > 0
        assert "D:/Projects/SAM" in results[0].fact.content
        assert results[0].similarity_score >= 0.4
    finally:
        mem.close()


def test_feat_mem_002_fuzzy_query_my_notes():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("My COA notes are in D:/Notes/COA", category="study")
        results = mem.search_facts("where are my notes?")
        assert len(results) > 0
        assert "D:/Notes/COA" in results[0].fact.content
    finally:
        mem.close()


def test_feat_mem_002_filters_below_threshold():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("My COA notes are in D:/Notes/COA", category="study")
        results = mem.search_facts("completely unrelated baking recipe for chocolate cake", min_score=0.7)
        assert len(results) == 0
    finally:
        mem.close()


def test_feat_mem_002_ranks_most_similar_first():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("Random groceries list", category="home")
        mem.store_fact("COA lecture notes and exam study material in D:/Notes/COA", category="study")
        results = mem.search_facts("COA notes exam", top_k=2)
        assert len(results) > 0
        assert "COA" in results[0].fact.content
    finally:
        mem.close()


def test_feat_mem_002_handles_empty_query():
    mem = MemoryEngineAdapter()
    try:
        results = mem.search_facts("")
        assert results == []
    finally:
        mem.close()
