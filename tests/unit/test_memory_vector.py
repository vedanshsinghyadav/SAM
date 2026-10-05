"""
Unit Test Suite for SAM Vector & Semantic Retrieval Engine.
Validates:
- Cosine similarity math (identical, orthogonal, opposite, zero, mismatched)
- IEEE 754 binary serialization & deserialization roundtrip
- Ollama embedding client graceful failover
- Offline heuristic scorer (fuzzy recall, ranking, filters, boundaries, Unicode Hindi)
- VectorMemoryEngine ranking and top-k filtering
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch
import pytest

from src.sam.memory.interface import MemoryFact, MemorySearchResult
from src.sam.memory.vector import (
    OfflineHeuristicScorer,
    OllamaEmbeddingClient,
    VectorMemoryEngine,
    cosine_similarity,
    deserialize_embedding,
    serialize_embedding,
)


# ============================================================================
# 1. Cosine Similarity Math Tests
# ============================================================================

class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        sim = cosine_similarity(vec, vec)
        assert math.isclose(sim, 1.0, rel_tol=1e-5)

    def test_orthogonal_vectors(self):
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == 0.0

    def test_opposite_vectors_clamped_to_zero(self):
        vec_a = [1.0, 2.0]
        vec_b = [-1.0, -2.0]
        # Opposite direction produces negative cosine, clamped to 0.0
        assert cosine_similarity(vec_a, vec_b) == 0.0

    def test_zero_vectors_no_division_by_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_mismatched_lengths(self):
        assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0


# ============================================================================
# 2. Embedding Serialization Roundtrip Tests
# ============================================================================

class TestEmbeddingSerialization:
    def test_roundtrip_floats(self):
        original = [0.1234, -0.5678, 1.0, 0.0, 42.42]
        blob = serialize_embedding(original)
        assert blob is not None
        assert len(blob) == len(original) * 4
        recovered = deserialize_embedding(blob)
        assert recovered is not None
        assert len(recovered) == len(original)
        for orig, rec in zip(original, recovered):
            assert math.isclose(orig, rec, rel_tol=1e-5)

    def test_none_and_empty_inputs(self):
        assert serialize_embedding(None) is None
        assert serialize_embedding([]) is None
        assert deserialize_embedding(None) is None
        assert deserialize_embedding(b"") is None


# ============================================================================
# 3. Ollama Embedding Client
# ============================================================================

class TestOllamaEmbeddingClient:
    def test_offline_unreachable_endpoint_returns_none(self):
        client = OllamaEmbeddingClient(base_url="http://localhost:59999", timeout=0.05)
        res = client.get_embedding("Test prompt")
        assert res is None

    def test_empty_text_returns_none(self):
        client = OllamaEmbeddingClient()
        assert client.get_embedding("") is None
        assert client.get_embedding("   ") is None

    def test_mock_successful_embedding_and_cache(self):
        client = OllamaEmbeddingClient()
        mock_vec = [0.1, 0.2, 0.3]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embedding": mock_vec}

        with patch("httpx.Client.post", return_value=mock_resp):
            res = client.get_embedding("Hello world")
            assert res == mock_vec
            # Second call should be served from memory cache without HTTP call
            with patch("httpx.Client.post") as mock_post:
                cached = client.get_embedding("Hello world")
                assert cached == mock_vec
                mock_post.assert_not_called()


# ============================================================================
# 4. Offline Heuristic Scorer Tests
# ============================================================================

class TestOfflineHeuristicScorer:
    def test_fuzzy_project_folder(self):
        doc = "Primary project SAM source code is at D:/Projects/SAM"
        score = OfflineHeuristicScorer.score("project folder", doc)
        assert score >= 0.40, f"Expected score >= 0.40, got {score}"

    def test_fuzzy_where_are_my_notes(self):
        doc = "My COA notes are in D:/Notes/COA"
        score = OfflineHeuristicScorer.score("where are my notes?", doc)
        assert score >= 0.40, f"Expected score >= 0.40, got {score}"

    def test_ranks_relevant_before_irrelevant(self):
        doc_target = "COA lecture notes and exam study material in D:/Notes/COA"
        doc_other = "Random groceries list"
        query = "COA notes exam"
        score_target = OfflineHeuristicScorer.score(query, doc_target)
        score_other = OfflineHeuristicScorer.score(query, doc_other)
        assert score_target > score_other
        assert score_target >= 0.70
        assert score_other < 0.10

    def test_filters_unrelated_query(self):
        doc = "My COA notes are in D:/Notes/COA"
        query = "completely unrelated baking recipe for chocolate cake"
        score = OfflineHeuristicScorer.score(query, doc)
        assert score < 0.40

    def test_empty_queries(self):
        assert OfflineHeuristicScorer.score("", "Some content") == 0.0
        assert OfflineHeuristicScorer.score("   ", "Some content") == 0.0
        assert OfflineHeuristicScorer.score("query", "") == 0.0

    def test_single_character_query(self):
        score = OfflineHeuristicScorer.score("a", "Single character test")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_sql_injection_robert(self):
        doc = "Robert'); DROP TABLE facts;--"
        score = OfflineHeuristicScorer.score("Robert", doc)
        assert score >= 0.40, f"Expected score >= 0.40 for Robert, got {score}"

    def test_editor_query_recall(self):
        doc = "User's primary editor is VS Code"
        score = OfflineHeuristicScorer.score("editor", doc)
        assert score >= 0.40, f"Expected score >= 0.40 for editor, got {score}"

    def test_unicode_hindi_fuzzy_match(self):
        doc = "COA के नोट्स यहाँ हैं: D:/Notes/COA"
        score = OfflineHeuristicScorer.score("COA नोट्स", doc)
        assert score >= 0.40, f"Expected score >= 0.40 for Unicode Hindi, got {score}"

    def test_exact_match_boundary_1_0(self):
        doc = "exact sentence match here"
        assert OfflineHeuristicScorer.score(doc, doc) == 1.0
        assert OfflineHeuristicScorer.score("different tokens", doc) < 1.0


# ============================================================================
# 5. VectorMemoryEngine End-to-End Tests
# ============================================================================

class TestVectorMemoryEngine:
    def test_rank_and_filter_empty_query(self):
        engine = VectorMemoryEngine(enable_ollama=False)
        facts = [MemoryFact(id=1, content="Some fact")]
        assert engine.rank_and_filter("", facts) == []
        assert engine.rank_and_filter("   ", facts) == []

    def test_rank_and_filter_top_k_ordering(self):
        engine = VectorMemoryEngine(enable_ollama=False)
        facts = [
            MemoryFact(id=1, content="COA notes unit 1"),
            MemoryFact(id=2, content="COA notes unit 2 complete"),
            MemoryFact(id=3, content="Irrelevant grocery receipt"),
        ]
        results = engine.rank_and_filter("COA notes", facts, top_k=2, min_score=0.40)
        assert len(results) == 2
        assert results[0].similarity_score >= results[1].similarity_score
        assert results[0].fact.id in [1, 2]

    def test_rank_and_filter_min_score_zero(self):
        engine = VectorMemoryEngine(enable_ollama=False)
        facts = [
            MemoryFact(id=1, content="COA notes in D:/Notes/COA"),
            MemoryFact(id=2, content="Baking recipe for cookies"),
        ]
        results = engine.rank_and_filter("notes", facts, min_score=0.0)
        assert len(results) == 2

    def test_rank_and_filter_min_score_one(self):
        engine = VectorMemoryEngine(enable_ollama=False)
        facts = [
            MemoryFact(id=1, content="exact matching string"),
            MemoryFact(id=2, content="approximate matching string"),
        ]
        results = engine.rank_and_filter("exact matching string", facts, min_score=1.0)
        assert len(results) == 1
        assert results[0].fact.id == 1
        assert results[0].similarity_score == 1.0

    def test_vector_scoring_with_mock_embeddings(self):
        engine = VectorMemoryEngine(enable_ollama=False)
        facts = [
            MemoryFact(id=1, content="Fact 1"),
            MemoryFact(id=2, content="Fact 2"),
        ]
        # Vectors where fact 1 has higher dot product
        embeddings = {
            1: [1.0, 0.0, 0.0],
            2: [0.0, 1.0, 0.0],
        }
        with patch.object(engine, "compute_embedding", return_value=[1.0, 0.0, 0.0]):
            results = engine.rank_and_filter("Fact 1", facts, top_k=2, min_score=0.1, fact_embeddings=embeddings)
            assert len(results) >= 1
            assert results[0].fact.id == 1
            assert math.isclose(results[0].similarity_score, 1.0, rel_tol=1e-5)
