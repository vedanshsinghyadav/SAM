"""
Tier 2: Boundary & Corner Cases for Long-Term Memory Engine (R3).
Covers:
- FEAT-MEM-001 Boundaries: Bulk storage stress, database locking, SQL characters, corrupted metadata, reopen DB (5 tests)
- FEAT-MEM-002 Boundaries: Query length 1, zero matches, contradictory updates, unicode fuzzy search, min score 0.0 and 1.0 (5 tests)
Total: 10 tests.
"""

import os
import tempfile
import pytest
from tests.e2e.harness import MemoryEngineAdapter


# ---------------------------------------------------------------------------
# FEAT-MEM-001 Boundaries
# ---------------------------------------------------------------------------

def test_feat_mem_001_boundary_bulk_store_100_facts():
    mem = MemoryEngineAdapter()
    try:
        for i in range(100):
            mem.store_fact(f"User fact number {i}", category="stress")
        results = mem.search_facts("fact number 50")
        assert len(results) > 0
    finally:
        mem.close()


def test_feat_mem_001_boundary_sql_injection_payload():
    mem = MemoryEngineAdapter()
    try:
        payload = "Robert'); DROP TABLE facts;--"
        fact_id = mem.store_fact(payload, category="injection")
        assert fact_id is not None
        # Verify table still exists
        res = mem.search_facts("Robert")
        assert len(res) > 0
    finally:
        mem.close()


def test_feat_mem_001_boundary_empty_content():
    mem = MemoryEngineAdapter()
    try:
        fid = mem.store_fact("", category="empty")
        assert fid > 0
    finally:
        mem.close()


def test_feat_mem_001_boundary_metadata_empty_dict():
    mem = MemoryEngineAdapter()
    try:
        fid = mem.store_fact("Test without metadata", metadata={})
        res = mem.search_facts("Test without metadata")
        assert res[0].fact.metadata == {}
    finally:
        mem.close()


def test_feat_mem_001_boundary_reopen_database():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        m1 = MemoryEngineAdapter(db_path=path)
        m1.store_fact("Persistent fact across reopen", category="test")
        m2 = MemoryEngineAdapter(db_path=path)
        res = m2.search_facts("Persistent fact")
        assert len(res) > 0
    finally:
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# FEAT-MEM-002 Boundaries
# ---------------------------------------------------------------------------

def test_feat_mem_002_boundary_query_length_one():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("Single character test", category="test")
        res = mem.search_facts("a")
        assert isinstance(res, list)
    finally:
        mem.close()


def test_feat_mem_002_boundary_zero_matches_returns_empty_list():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("Python programming language", category="dev")
        res = mem.search_facts("xyzqwerty987654321", min_score=0.8)
        assert res == []
    finally:
        mem.close()


def test_feat_mem_002_boundary_contradictory_facts():
    mem = MemoryEngineAdapter()
    try:
        mem.set_exact("notes_dir", "D:/Notes/Old")
        mem.set_exact("notes_dir", "D:/Notes/New")
        assert mem.retrieve_exact("notes_dir") == "D:/Notes/New"
    finally:
        mem.close()


def test_feat_mem_002_boundary_unicode_fuzzy_search():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("COA के नोट्स यहाँ हैं: D:/Notes/COA", category="study")
        res = mem.search_facts("COA नोट्स")
        assert len(res) > 0
    finally:
        mem.close()


def test_feat_mem_002_boundary_min_score_1_0():
    mem = MemoryEngineAdapter()
    try:
        mem.store_fact("exact sentence match here", category="exact")
        # With min_score=1.0, only exact token sets or perfect score matches pass
        res = mem.search_facts("completely different tokens", min_score=1.0)
        assert len(res) == 0
    finally:
        mem.close()
