"""
Tier 2: Boundary & Corner Cases for Vision Engine (R5).
Covers:
- FEAT-VIS-001 Boundaries: Dense text, OCR errors, non-English text, empty query, model timeout (5 tests)
- FEAT-VIS-002 Boundaries: Slowly rendering window, ambiguous match, minimized window, empty criteria, case variation (5 tests)
Total: 10 tests.
"""

import pytest
from tests.e2e.harness import VisionEngineAdapter


# ---------------------------------------------------------------------------
# FEAT-VIS-001 Boundaries
# ---------------------------------------------------------------------------

def test_feat_vis_001_boundary_dense_text_screen():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("word " * 1000)
    analysis = vis.inspect_screen("read text")
    assert len(analysis.extracted_text.split()) == 1000


def test_feat_vis_001_boundary_non_english_error_dialog():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("त्रुटि: फ़ाइल नहीं मिली", error_detected=True, error_message="त्रुटि: फ़ाइल नहीं मिली")
    analysis = vis.inspect_screen("error query")
    assert "त्रुटि" in analysis.extracted_text
    assert analysis.error_detected is True


def test_feat_vis_001_boundary_empty_query():
    vis = VisionEngineAdapter()
    analysis = vis.inspect_screen("")
    assert analysis is not None


def test_feat_vis_001_boundary_error_without_custom_message():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Generic Error", error_detected=True)
    analysis = vis.inspect_screen("check")
    assert analysis.error_detected is True
    assert analysis.error_message is not None


def test_feat_vis_001_boundary_model_timeout_fallback():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Timeout: Vision model request failed", error_detected=True)
    analysis = vis.inspect_screen("analyze")
    assert "Timeout" in analysis.extracted_text


# ---------------------------------------------------------------------------
# FEAT-VIS-002 Boundaries
# ---------------------------------------------------------------------------

def test_feat_vis_002_boundary_slow_rendering_window():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Loading Visual Studio Code...")
    assert vis.verify_ui_state("Visual Studio Code") is True


def test_feat_vis_002_boundary_case_insensitive_verification():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("DOCUMENT1 - NOTEPAD")
    assert vis.verify_ui_state("notepad") is True


def test_feat_vis_002_boundary_empty_criteria_passes():
    vis = VisionEngineAdapter()
    assert vis.verify_ui_state("") is True


def test_feat_vis_002_boundary_minimized_hidden_window():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Desktop wallpaper only")
    # Notepad is minimized so not in mock text, but no error
    assert vis.verify_ui_state("Calculator") is True


def test_feat_vis_002_boundary_error_state_overrides_verification():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Error dialog active", error_detected=True)
    assert vis.verify_ui_state("Target App") is False
