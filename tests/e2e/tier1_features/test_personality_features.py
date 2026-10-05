"""
Tier 1: Feature Coverage Tests for Personality Engine (R8).
Covers:
- FEAT-PERS-001: Context-Adaptive Dual-Tone (5 tests)
- FEAT-PERS-002: Modality-Invariant Persona (5 tests)
Total: 10 tests.
"""

import pytest
from tests.e2e.harness import PersonalityAdapter


# ---------------------------------------------------------------------------
# FEAT-PERS-001: Context-Adaptive Dual-Tone
# ---------------------------------------------------------------------------

def test_feat_pers_001_casual_cpu_query_includes_wit():
    pers = PersonalityAdapter()
    resp = pers.adapt_tone("CPU is currently at 18.5%.", is_task=False)
    assert "18.5%" in resp
    assert "silicon" in resp.lower() or "sweat" in resp.lower()


def test_feat_pers_001_task_execution_is_concise():
    pers = PersonalityAdapter()
    resp = pers.adapt_tone("Moved file to D:/Notes/COA", is_task=True)
    assert resp.strip() == "Moved file to D:/Notes/COA."
    assert "sweat" not in resp


def test_feat_pers_001_casual_greeting_is_friendly():
    pers = PersonalityAdapter()
    resp = pers.adapt_tone("Hello there", is_task=False)
    assert "Greetings" in resp or "service" in resp


def test_feat_pers_001_task_mode_avoids_chatty_additions():
    pers = PersonalityAdapter()
    resp = pers.adapt_tone("Opening Chrome", is_task=True)
    assert resp == "Opening Chrome."


def test_feat_pers_001_preserves_informational_facts():
    pers = PersonalityAdapter()
    raw = "Found 3 PDF files in Downloads"
    resp = pers.adapt_tone(raw, is_task=True)
    assert raw in resp


# ---------------------------------------------------------------------------
# FEAT-PERS-002: Modality-Invariant Persona
# ---------------------------------------------------------------------------

def test_feat_pers_002_text_mode_preserves_content():
    pers = PersonalityAdapter()
    txt = "Volume set to 50%."
    formatted = pers.format_response(txt, modality="text")
    assert formatted == txt


def test_feat_pers_002_voice_mode_preserves_content():
    pers = PersonalityAdapter()
    txt = "Volume set to 50%."
    formatted = pers.format_response(txt, modality="voice")
    assert formatted == txt


def test_feat_pers_002_identical_response_across_modalities():
    pers = PersonalityAdapter()
    resp = "Navigating to YouTube."
    text_out = pers.format_response(resp, modality="text")
    voice_out = pers.format_response(resp, modality="voice")
    assert text_out == voice_out


def test_feat_pers_002_handles_whitespace_identically():
    pers = PersonalityAdapter()
    resp = "  All tasks completed.  "
    assert pers.format_response(resp, modality="text") == "All tasks completed."
    assert pers.format_response(resp, modality="voice") == "All tasks completed."


def test_feat_pers_002_character_consistency():
    pers = PersonalityAdapter()
    toned = pers.adapt_tone("CPU is 12%", is_task=False)
    text_v = pers.format_response(toned, modality="text")
    voice_v = pers.format_response(toned, modality="voice")
    assert text_v == voice_v
