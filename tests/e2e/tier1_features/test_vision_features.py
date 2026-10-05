"""
Tier 1: Feature Coverage Tests for Vision Engine (R5).
Covers:
- FEAT-VIS-001: Screen Understanding & QA (5 tests)
- FEAT-VIS-002: Visual Action Verifier (5 tests)
Total: 10 tests.
"""

import pytest
from tests.e2e.harness import VisionEngineAdapter


# ---------------------------------------------------------------------------
# FEAT-VIS-001: Screen Understanding & QA
# ---------------------------------------------------------------------------

def test_feat_vis_001_inspect_screen_normal_state():
    vis = VisionEngineAdapter()
    analysis = vis.inspect_screen("Describe screen")
    assert analysis.error_detected is False
    assert "Desktop" in analysis.extracted_text


def test_feat_vis_001_detect_and_extract_error_dialog():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Error 404: Not Found", error_detected=True, error_message="Error 404: Not Found")
    analysis = vis.inspect_screen("What does this error say?")
    assert analysis.error_detected is True
    assert "Error 404: Not Found" in analysis.extracted_text


def test_feat_vis_001_description_field_populated():
    vis = VisionEngineAdapter()
    analysis = vis.inspect_screen("Check window layout")
    assert len(analysis.description) > 0


def test_feat_vis_001_error_message_captured():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("FileNotFoundError: syllabus.txt", error_detected=True, error_message="FileNotFoundError: syllabus.txt")
    analysis = vis.inspect_screen("Any errors?")
    assert analysis.error_message == "FileNotFoundError: syllabus.txt"


def test_feat_vis_001_empty_screen_query_handled():
    vis = VisionEngineAdapter()
    analysis = vis.inspect_screen("")
    assert analysis is not None
    assert isinstance(analysis.extracted_text, str)


# ---------------------------------------------------------------------------
# FEAT-VIS-002: Visual Action Verifier
# ---------------------------------------------------------------------------

def test_feat_vis_002_verify_matching_ui_state():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Notepad - document1.txt")
    passed = vis.verify_ui_state("Notepad")
    assert passed is True


def test_feat_vis_002_verify_fails_on_active_error():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Crash Error", error_detected=True)
    passed = vis.verify_ui_state("Chrome")
    assert passed is False


def test_feat_vis_002_verify_empty_criteria_passes():
    vis = VisionEngineAdapter()
    passed = vis.verify_ui_state("")
    assert passed is True


def test_feat_vis_002_verify_case_insensitive_match():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("spotify premium active")
    passed = vis.verify_ui_state("Spotify")
    assert passed is True


def test_feat_vis_002_verify_partial_string_match():
    vis = VisionEngineAdapter()
    vis.set_mock_screen_state("Google Chrome - New Tab")
    passed = vis.verify_ui_state("New Tab")
    assert passed is True
