"""
Tier 1: Feature Coverage Tests for Safety Guard & Risk Engine (R7).
Covers:
- FEAT-SAFE-001: Tri-Tier Risk Classification (5 tests)
- FEAT-SAFE-002: Low-Risk Immediate Dispatch (5 tests)
- FEAT-SAFE-003: Medium-Risk Announcement (5 tests)
- FEAT-SAFE-004: High-Risk Confirmation Guard (5 tests)
Total: 20 tests.
"""

import pytest
from tests.e2e.harness import SafetyGuardAdapter, ToolCall, RiskLevel


# ---------------------------------------------------------------------------
# FEAT-SAFE-001: Tri-Tier Risk Classification
# ---------------------------------------------------------------------------

def test_feat_safe_001_classify_low_risk_open_app():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="open_app", arguments={"app_name": "Chrome"}))
    assert risk == RiskLevel.LOW


def test_feat_safe_001_classify_low_risk_volume():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="control_volume", arguments={"level": 50}))
    assert risk == RiskLevel.LOW


def test_feat_safe_001_classify_medium_risk_move_file():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="move_file", arguments={"src": "a", "dst": "b"}))
    assert risk == RiskLevel.MEDIUM


def test_feat_safe_001_classify_medium_risk_close_app():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="close_app", arguments={"process_or_name": "Spotify"}))
    assert risk == RiskLevel.MEDIUM


def test_feat_safe_001_classify_high_risk_delete_files():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="delete_files", arguments={"path": "Downloads"}))
    assert risk == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# FEAT-SAFE-002: Low-Risk Immediate Dispatch
# ---------------------------------------------------------------------------

def test_feat_safe_002_low_risk_authorizes_without_user_confirmation():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="open_app", arguments={"app_name": "Chrome"}, risk_level=RiskLevel.LOW)
    authorized, reason = safety.authorize(tc, user_confirmed=False)
    assert authorized is True
    assert "Authorized" in reason


def test_feat_safe_002_low_risk_brightness_immediate():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="control_brightness", arguments={"level": 70})
    authorized, _ = safety.authorize(tc, user_confirmed=False)
    assert authorized is True


def test_feat_safe_002_low_risk_media_play_immediate():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="media_play", arguments={"command": "play"})
    authorized, _ = safety.authorize(tc, user_confirmed=False)
    assert authorized is True


def test_feat_safe_002_low_risk_no_announcements_logged():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="open_app", arguments={"app_name": "Notepad"})
    safety.authorize(tc, user_confirmed=False)
    assert len(safety.announcements) == 0


def test_feat_safe_002_low_risk_user_confirmation_ignored():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="open_app", arguments={"app_name": "Chrome"})
    auth_true, _ = safety.authorize(tc, user_confirmed=True)
    auth_false, _ = safety.authorize(tc, user_confirmed=False)
    assert auth_true is True
    assert auth_false is True


# ---------------------------------------------------------------------------
# FEAT-SAFE-003: Medium-Risk Announcement
# ---------------------------------------------------------------------------

def test_feat_safe_003_medium_risk_logs_announcement():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="close_app", arguments={"process_or_name": "Spotify"})
    auth, msg = safety.authorize(tc, user_confirmed=False)
    assert auth is True
    assert len(safety.announcements) == 1
    assert "Announcing" in safety.announcements[0]


def test_feat_safe_003_medium_risk_move_file_announces():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="move_file", arguments={"src": "a", "dst": "b"})
    safety.authorize(tc, user_confirmed=False)
    assert any("move_file" in a for a in safety.announcements)


def test_feat_safe_003_medium_risk_allows_execution_after_announcement():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="install_software", arguments={"package": "node"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is True


def test_feat_safe_003_medium_risk_terminal_runner_announces():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="run_terminal", arguments={"command": "dir"})
    auth, msg = safety.authorize(tc, user_confirmed=False)
    assert auth is True
    assert "run_terminal" in msg


def test_feat_safe_003_medium_risk_multiple_announcements():
    safety = SafetyGuardAdapter()
    safety.authorize(ToolCall(tool_name="move_file"), user_confirmed=False)
    safety.authorize(ToolCall(tool_name="close_app"), user_confirmed=False)
    assert len(safety.announcements) == 2


# ---------------------------------------------------------------------------
# FEAT-SAFE-004: High-Risk Confirmation Guard
# ---------------------------------------------------------------------------

def test_feat_safe_004_high_risk_blocked_without_confirmation():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
    auth, reason = safety.authorize(tc, user_confirmed=False)
    assert auth is False
    assert "Blocked" in reason
    assert "requires explicit confirmation" in reason


def test_feat_safe_004_high_risk_authorized_when_user_confirms():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
    auth, reason = safety.authorize(tc, user_confirmed=True)
    assert auth is True
    assert "Authorized: User confirmed" in reason


def test_feat_safe_004_high_risk_format_disk_blocked():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="format_disk", arguments={"drive": "C:"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is False


def test_feat_safe_004_high_risk_send_message_blocked():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="send_message", arguments={"recipient": "all", "text": "test"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is False


def test_feat_safe_004_high_risk_no_leakage_to_announcements():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
    safety.authorize(tc, user_confirmed=False)
    assert len(safety.announcements) == 0
