"""
Unit Test Suite for SAM Safety and Permission Guard (src/sam/safety/).
Tests:
1. Protocol adherence and state initialization
2. Tri-tier risk classification taxonomy and heuristics
3. Dangerous command and sensitive path escalation
4. Non-downgrade defense-in-depth policy
5. Authorization workflows for LOW, MEDIUM, HIGH risk levels
6. Announcement tracking and isolation
7. Confirmation prompt formulation and affirmative response evaluation
"""

import pytest
from src.sam.common.types import ToolCall, RiskLevel
from src.sam.safety.interface import ISafetyGuard
from src.sam.safety.guard import SafetyGuard


class TestSafetyProtocolAndInit:
    """Verify protocol compliance and clean initialization."""

    def test_implements_isafety_guard_protocol(self):
        guard = SafetyGuard()
        assert isinstance(guard, ISafetyGuard)

    def test_announcements_initializes_empty(self):
        guard = SafetyGuard()
        assert guard.announcements == []
        assert isinstance(guard.announcements, list)


class TestRiskClassification:
    """Verify tri-tier categorization logic."""

    @pytest.mark.parametrize("tool_name", [
        "open_app", "control_volume", "control_brightness",
        "media_play", "find_files", "inspect_screen", "",
    ])
    def test_classify_low_risk_tools(self, tool_name):
        guard = SafetyGuard()
        tc = ToolCall(tool_name=tool_name)
        assert guard.classify_risk(tc) == RiskLevel.LOW

    @pytest.mark.parametrize("tool_name", [
        "move_file", "rename_file", "close_app",
        "terminate_process", "install_software", "run_terminal",
    ])
    def test_classify_medium_risk_tools(self, tool_name):
        guard = SafetyGuard()
        tc = ToolCall(tool_name=tool_name)
        assert guard.classify_risk(tc) == RiskLevel.MEDIUM

    @pytest.mark.parametrize("tool_name", [
        "delete_files", "delete_file", "format_disk",
        "send_message", "execute_sensitive_cmd", "wipe_system_cache",
    ])
    def test_classify_high_risk_tools(self, tool_name):
        guard = SafetyGuard()
        tc = ToolCall(tool_name=tool_name)
        assert guard.classify_risk(tc) == RiskLevel.HIGH

    def test_classify_case_insensitivity(self):
        guard = SafetyGuard()
        assert guard.classify_risk(ToolCall(tool_name="DELETE_FILES")) == RiskLevel.HIGH
        assert guard.classify_risk(ToolCall(tool_name="Move_File")) == RiskLevel.MEDIUM
        assert guard.classify_risk(ToolCall(tool_name="Open_App")) == RiskLevel.LOW

    def test_classify_keyword_heuristics(self):
        guard = SafetyGuard()
        assert guard.classify_risk(ToolCall(tool_name="destroy_everything")) == RiskLevel.HIGH
        assert guard.classify_risk(ToolCall(tool_name="wipe_temporary_data")) == RiskLevel.HIGH
        assert guard.classify_risk(ToolCall(tool_name="nuke_database")) == RiskLevel.HIGH

    def test_classify_terminal_dangerous_commands(self):
        guard = SafetyGuard()
        tc_safe = ToolCall(tool_name="run_terminal", arguments={"command": "dir"})
        assert guard.classify_risk(tc_safe) == RiskLevel.MEDIUM

        tc_rm = ToolCall(tool_name="run_terminal", arguments={"command": "rmdir /s /q C:\\data"})
        assert guard.classify_risk(tc_rm) == RiskLevel.HIGH

        tc_format = ToolCall(tool_name="run_terminal", arguments={"command": "format D: /fs:NTFS"})
        assert guard.classify_risk(tc_format) == RiskLevel.HIGH

        tc_enc = ToolCall(tool_name="run_terminal", arguments={"command": "powershell -enc AAAA"})
        assert guard.classify_risk(tc_enc) == RiskLevel.HIGH

    def test_classify_sensitive_system_paths(self):
        guard = SafetyGuard()
        tc_sys = ToolCall(tool_name="copy_file", arguments={"src": "a", "dst": "C:\\Windows\\System32\\driver.sys"})
        assert guard.classify_risk(tc_sys) == RiskLevel.HIGH

    def test_risk_non_downgrade_guarantee(self):
        guard = SafetyGuard()
        # Attempt to downgrade high-risk tool to LOW
        tc_sneak = ToolCall(tool_name="delete_files", risk_level=RiskLevel.LOW)
        assert guard.classify_risk(tc_sneak) == RiskLevel.HIGH

        # Caller can safely elevate risk
        tc_elevate = ToolCall(tool_name="open_app", risk_level=RiskLevel.HIGH)
        assert guard.classify_risk(tc_elevate) == RiskLevel.HIGH


class TestAuthorizationWorkflows:
    """Verify authorization behavior per risk tier."""

    def test_low_risk_immediate_dispatch(self):
        guard = SafetyGuard()
        tc = ToolCall(tool_name="open_app", arguments={"app_name": "Chrome"})
        auth, reason = guard.authorize(tc, user_confirmed=False)
        assert auth is True
        assert "Authorized" in reason
        assert len(guard.announcements) == 0

    def test_low_risk_burst_dispatch(self):
        guard = SafetyGuard()
        tc = ToolCall(tool_name="control_volume", arguments={"level": 50})
        for _ in range(100):
            auth, _ = guard.authorize(tc, user_confirmed=False)
            assert auth is True
        assert len(guard.announcements) == 0

    def test_medium_risk_logs_announcement(self):
        guard = SafetyGuard()
        tc = ToolCall(tool_name="close_app", arguments={"process_or_name": "Spotify"})
        auth, msg = guard.authorize(tc, user_confirmed=False)
        assert auth is True
        assert "Announcing" in msg
        assert "close_app" in msg
        assert len(guard.announcements) == 1
        assert "close_app" in guard.announcements[0]

    def test_medium_risk_multiple_and_clear(self):
        guard = SafetyGuard()
        guard.authorize(ToolCall(tool_name="move_file"), user_confirmed=False)
        guard.authorize(ToolCall(tool_name="rename_file"), user_confirmed=False)
        assert len(guard.announcements) == 2
        guard.announcements.clear()
        assert len(guard.announcements) == 0

    def test_high_risk_blocked_without_confirmation(self):
        guard = SafetyGuard()
        tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
        auth, reason = guard.authorize(tc, user_confirmed=False)
        assert auth is False
        assert "Blocked" in reason
        assert "requires explicit confirmation" in reason
        assert len(guard.announcements) == 0

    def test_high_risk_authorized_on_boolean_true(self):
        guard = SafetyGuard()
        tc = ToolCall(tool_name="delete_files", arguments={"path": "Downloads"})
        auth, reason = guard.authorize(tc, user_confirmed=True)
        assert auth is True
        assert "Authorized: User confirmed" in reason
        assert len(guard.announcements) == 0

    def test_high_risk_strict_boolean_check(self):
        guard = SafetyGuard()
        tc = ToolCall(tool_name="delete_files")
        # Non-boolean values must not authorize
        auth1, _ = guard.authorize(tc, user_confirmed="yes")  # type: ignore
        assert auth1 is False
        auth2, _ = guard.authorize(tc, user_confirmed=1)  # type: ignore
        assert auth2 is False
        auth3, _ = guard.authorize(tc, user_confirmed=None)  # type: ignore
        assert auth3 is False


class TestConfirmationPromptAndAffirmativeParser:
    """Verify prompt formatting and affirmative utterance parsing."""

    def test_confirmation_prompt_formatting(self):
        guard = SafetyGuard()
        p_del = guard.generate_confirmation_prompt(ToolCall(tool_name="delete_files", arguments={"path": "Downloads"}))
        assert "delete all files in Downloads" in p_del

        p_fmt = guard.generate_confirmation_prompt(ToolCall(tool_name="format_disk", arguments={"drive": "D:"}))
        assert "format disk D:" in p_fmt

        p_msg = guard.generate_confirmation_prompt(ToolCall(tool_name="send_message", arguments={"recipient": "Vedant"}))
        assert "send message to 'Vedant'" in p_msg

        p_cmd = guard.generate_confirmation_prompt(ToolCall(tool_name="run_terminal", arguments={"command": "rmdir C:\\test"}))
        assert "execute command 'rmdir C:\\test'" in p_cmd

    @pytest.mark.parametrize("affirmative", [
        "confirm", "confirmed", "yes", "y", "yeah", "yep", "sure", "proceed",
        "haan", "kar do", "bilkul", "yes please",
    ])
    def test_is_affirmative_confirmation(self, affirmative):
        guard = SafetyGuard()
        assert guard.is_affirmative_confirmation(affirmative) is True

    @pytest.mark.parametrize("negative", [
        "no", "n", "nope", "cancel", "stop", "abort", "never", "don't",
        "nahi", "mat karo", "roko",
    ])
    def test_is_negative_confirmation(self, negative):
        guard = SafetyGuard()
        assert guard.is_affirmative_confirmation(negative) is False

    def test_negation_precedence_in_affirmative_check(self):
        guard = SafetyGuard()
        # If user says "no don't proceed", negative must win
        assert guard.is_affirmative_confirmation("no proceed") is False
        assert guard.is_affirmative_confirmation("") is False
        assert guard.is_affirmative_confirmation(None) is False  # type: ignore
