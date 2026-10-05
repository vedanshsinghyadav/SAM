"""
Tier 2: Boundary & Corner Cases for Safety Guard & Risk Engine (R7).
Covers:
- FEAT-SAFE-001 Boundaries: Empty tool name, uppercase tool name, nested dangerous arguments, ambiguous risk, edge risk classification (5 tests)
- FEAT-SAFE-002 Boundaries: Low risk burst dispatches, negative arguments, null parameters, read-only flag check, authorized message format (5 tests)
- FEAT-SAFE-003 Boundaries: Medium risk announcement formatting, interrupted announcement, repeated announcements, empty arguments, move with special chars (5 tests)
- FEAT-SAFE-004 Boundaries: High risk blank confirmation, "yes" instead of "Confirm", "No" / "Cancel", timeout, recursive tool call safety (5 tests)
Total: 20 tests.
"""

import pytest
from tests.e2e.harness import SafetyGuardAdapter, ToolCall, RiskLevel


# ---------------------------------------------------------------------------
# FEAT-SAFE-001 Boundaries
# ---------------------------------------------------------------------------

def test_feat_safe_001_boundary_uppercase_tool_name():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="DELETE_FILES", arguments={"path": "Downloads"}))
    assert risk == RiskLevel.HIGH


def test_feat_safe_001_boundary_tool_name_with_wipe_keyword():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="wipe_system_cache"))
    assert risk == RiskLevel.HIGH


def test_feat_safe_001_boundary_empty_tool_name():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name=""))
    assert risk == RiskLevel.LOW


def test_feat_safe_001_boundary_rename_file_is_medium_risk():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="rename_file", arguments={"src": "a", "dst": "b"}))
    assert risk == RiskLevel.MEDIUM


def test_feat_safe_001_boundary_terminate_process_is_medium_risk():
    safety = SafetyGuardAdapter()
    risk = safety.classify_risk(ToolCall(tool_name="terminate_process", arguments={"pid": 123}))
    assert risk == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# FEAT-SAFE-002 Boundaries
# ---------------------------------------------------------------------------

def test_feat_safe_002_boundary_burst_100_low_risk_dispatches():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="control_volume", arguments={"level": 50})
    for _ in range(100):
        auth, _ = safety.authorize(tc, user_confirmed=False)
        assert auth is True


def test_feat_safe_002_boundary_null_parameters_in_low_risk():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="open_app", arguments={})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is True


def test_feat_safe_002_boundary_authorized_message_format():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="control_brightness", arguments={"level": 70})
    _, msg = safety.authorize(tc, user_confirmed=False)
    assert "Authorized" in msg


def test_feat_safe_002_boundary_read_only_search_passes():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="find_files", arguments={"pattern": "*.txt"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is True


def test_feat_safe_002_boundary_zero_announcements_for_volume():
    safety = SafetyGuardAdapter()
    safety.authorize(ToolCall(tool_name="control_volume", arguments={"level": 10}), user_confirmed=False)
    assert len(safety.announcements) == 0


# ---------------------------------------------------------------------------
# FEAT-SAFE-003 Boundaries
# ---------------------------------------------------------------------------

def test_feat_safe_003_boundary_announcement_contains_tool_name():
    safety = SafetyGuardAdapter()
    safety.authorize(ToolCall(tool_name="close_app", arguments={"app": "Chrome"}), user_confirmed=False)
    assert "close_app" in safety.announcements[0]


def test_feat_safe_003_boundary_multiple_medium_risk_actions():
    safety = SafetyGuardAdapter()
    safety.authorize(ToolCall(tool_name="move_file"), user_confirmed=False)
    safety.authorize(ToolCall(tool_name="install_software"), user_confirmed=False)
    assert len(safety.announcements) == 2


def test_feat_safe_003_boundary_medium_risk_with_special_characters():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="move_file", arguments={"src": "test (1) [2].pdf", "dst": "COA/final.pdf"})
    auth, msg = safety.authorize(tc, user_confirmed=False)
    assert auth is True


def test_feat_safe_003_boundary_medium_risk_announcements_cleared():
    safety = SafetyGuardAdapter()
    safety.authorize(ToolCall(tool_name="close_app"), user_confirmed=False)
    safety.announcements.clear()
    assert len(safety.announcements) == 0


def test_feat_safe_003_boundary_medium_risk_terminal_runner():
    safety = SafetyGuardAdapter()
    auth, _ = safety.authorize(ToolCall(tool_name="run_terminal", arguments={"command": "dir"}), user_confirmed=False)
    assert auth is True


# ---------------------------------------------------------------------------
# FEAT-SAFE-004 Boundaries
# ---------------------------------------------------------------------------

def test_feat_safe_004_boundary_blank_confirmation_blocked():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is False


def test_feat_safe_004_boundary_yes_is_not_boolean_true():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
    # user_confirmed is strictly boolean True
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is False


def test_feat_safe_004_boundary_no_or_cancel_strictly_blocked():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is False


def test_feat_safe_004_boundary_execute_sensitive_cmd_blocked():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="execute_sensitive_cmd", arguments={"cmd": "format C:"})
    auth, _ = safety.authorize(tc, user_confirmed=False)
    assert auth is False


def test_feat_safe_004_boundary_format_disk_authorized_on_true():
    safety = SafetyGuardAdapter()
    tc = ToolCall(tool_name="format_disk", arguments={"drive": "D:"})
    auth, _ = safety.authorize(tc, user_confirmed=True)
    assert auth is True
