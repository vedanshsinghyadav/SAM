"""
Tier 2: Boundary & Corner Cases for Personality Engine (R8).
Covers:
- FEAT-PERS-001 Boundaries: Empty response string, critical error message, code block preservation, 100% CPU overload, rapid mode oscillation (5 tests)
- FEAT-PERS-002 Boundaries: ANSI escapes in text, SSML speech markers, modality switch mid-conversation, multi-paragraph text, unicode punctuation (5 tests)
Total: 10 tests.
"""

import pytest
from tests.e2e.harness import PersonalityAdapter


# ---------------------------------------------------------------------------
# FEAT-PERS-001 Boundaries
# ---------------------------------------------------------------------------

def test_feat_pers_001_boundary_empty_string_adaptation():
    pers = PersonalityAdapter()
    res = pers.adapt_tone("", is_task=False)
    assert res == ""


def test_feat_pers_001_boundary_critical_error_message():
    pers = PersonalityAdapter()
    err = "Fatal: Device driver disconnected."
    res = pers.adapt_tone(err, is_task=True)
    assert err in res


def test_feat_pers_001_boundary_code_block_preservation():
    pers = PersonalityAdapter()
    code = "```python\nprint('hello')\n```"
    res = pers.adapt_tone(code, is_task=True)
    assert "print('hello')" in res


def test_feat_pers_001_boundary_cpu_at_100_percent():
    pers = PersonalityAdapter()
    res = pers.adapt_tone("CPU is at 100%.", is_task=False)
    assert "100%" in res


def test_feat_pers_001_boundary_rapid_mode_oscillation():
    pers = PersonalityAdapter()
    for _ in range(5):
        c = pers.adapt_tone("Hello", is_task=False)
        t = pers.adapt_tone("Opened Chrome", is_task=True)
        assert "Greetings" in c or "service" in c
        assert "Opened Chrome." == t


# ---------------------------------------------------------------------------
# FEAT-PERS-002 Boundaries
# ---------------------------------------------------------------------------

def test_feat_pers_002_boundary_ansi_escape_sequences():
    pers = PersonalityAdapter()
    raw = "\x1b[32mSuccess\x1b[0m"
    res = pers.format_response(raw, modality="text")
    assert "Success" in res


def test_feat_pers_002_boundary_ssml_markers_in_voice():
    pers = PersonalityAdapter()
    raw = "<speak>Hello user</speak>"
    res = pers.format_response(raw, modality="voice")
    assert "<speak>" in res


def test_feat_pers_002_boundary_multiline_paragraphs():
    pers = PersonalityAdapter()
    text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
    t_out = pers.format_response(text, modality="text")
    v_out = pers.format_response(text, modality="voice")
    assert t_out == v_out


def test_feat_pers_002_boundary_unicode_punctuation():
    pers = PersonalityAdapter()
    raw = "Done! «Success» — verified."
    t_out = pers.format_response(raw, modality="text")
    v_out = pers.format_response(raw, modality="voice")
    assert t_out == v_out == raw


def test_feat_pers_002_boundary_trailing_spaces():
    pers = PersonalityAdapter()
    raw = "    Text with spaces    "
    assert pers.format_response(raw, modality="text") == "Text with spaces"
    assert pers.format_response(raw, modality="voice") == "Text with spaces"
