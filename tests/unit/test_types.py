"""
Unit tests for src/sam/common/types.py.
Validates enums, data contracts, Pydantic schemas, and serialization roundtrips.
"""

import time
import pytest
from src.sam.common.types import (
    RiskLevel,
    ActionStatus,
    DecisionType,
    PersonalityMode,
    ToolCall,
    BrainDecision,
    ConversationTurn,
    ActiveContext,
    ExecutionResult,
    NetworkStatus,
)


class TestRiskLevel:
    def test_risk_level_values(self):
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.HIGH.value == "HIGH"

    def test_from_str(self):
        assert RiskLevel.from_str("low") == RiskLevel.LOW
        assert RiskLevel.from_str("MEDIUM") == RiskLevel.MEDIUM
        assert RiskLevel.from_str(" High ") == RiskLevel.HIGH

    def test_from_str_invalid(self):
        with pytest.raises(ValueError):
            RiskLevel.from_str("CRITICAL")

    def test_is_at_least(self):
        assert RiskLevel.HIGH.is_at_least(RiskLevel.MEDIUM) is True
        assert RiskLevel.MEDIUM.is_at_least(RiskLevel.LOW) is True
        assert RiskLevel.LOW.is_at_least(RiskLevel.HIGH) is False
        assert RiskLevel.MEDIUM.is_at_least(RiskLevel.MEDIUM) is True


class TestActionStatus:
    def test_status_values(self):
        assert ActionStatus.SUCCESS.value == "SUCCESS"
        assert ActionStatus.FAILURE.value == "FAILURE"
        assert ActionStatus.AWAITING_CONFIRMATION.value == "AWAITING_CONFIRMATION"
        assert ActionStatus.CANCELLED.value == "CANCELLED"
        assert ActionStatus.PENDING.value == "PENDING"
        assert ActionStatus.IN_PROGRESS.value == "IN_PROGRESS"


class TestToolCall:
    def test_tool_call_creation_and_defaults(self):
        tc = ToolCall(tool_name="open_app")
        assert tc.tool_name == "open_app"
        assert tc.arguments == {}
        assert tc.risk_level is None

    def test_tool_call_serialization(self):
        tc = ToolCall(
            tool_name="delete_files",
            arguments={"path": "C:/Downloads", "pattern": "*.tmp"},
            risk_level=RiskLevel.HIGH,
            call_id="call-001"
        )
        data = tc.to_dict()
        assert data["tool_name"] == "delete_files"
        assert data["risk_level"] == "HIGH"
        assert data["arguments"]["pattern"] == "*.tmp"

        reconstructed = ToolCall.from_dict(data)
        assert reconstructed.tool_name == tc.tool_name
        assert reconstructed.risk_level == RiskLevel.HIGH
        assert reconstructed.call_id == "call-001"

    def test_tool_call_model_dump_validate(self):
        tc = ToolCall(tool_name="volume_control", arguments={"level": 50})
        dumped = tc.model_dump()
        assert dumped["tool_name"] == "volume_control"
        loaded = ToolCall.model_validate(dumped)
        assert loaded.tool_name == "volume_control"
        assert loaded.arguments["level"] == 50


class TestBrainDecision:
    def test_reply_decision(self):
        d = BrainDecision(decision_type="reply", reply_text="Good morning, sir.")
        assert d.is_reply is True
        assert d.is_tool_call is False
        assert d.is_plan is False

    def test_tool_call_decision(self):
        tc = ToolCall(tool_name="open_app", arguments={"app": "chrome"})
        d = BrainDecision(decision_type="tool_call", tool_call=tc)
        assert d.is_reply is False
        assert d.is_tool_call is True
        assert d.tool_call.tool_name == "open_app"

    def test_plan_decision(self):
        d = BrainDecision(decision_type="plan", plan_goal="Study COA exam")
        assert d.is_plan is True
        assert d.plan_goal == "Study COA exam"

    def test_confirmation_flags(self):
        d = BrainDecision(
            decision_type="tool_call",
            tool_call=ToolCall(tool_name="delete_all"),
            requires_confirmation=True,
            confirmation_prompt="Confirm deleting all files?"
        )
        assert d.requires_confirmation is True
        assert d.confirmation_prompt == "Confirm deleting all files?"

    def test_roundtrip_serialization(self):
        d = BrainDecision(
            decision_type="tool_call",
            reply_text="Executing action",
            tool_call=ToolCall(tool_name="open_app", arguments={"app_name": "chrome"}),
            is_offline_fallback=True
        )
        data = d.to_dict()
        restored = BrainDecision.from_dict(data)
        assert restored.decision_type == "tool_call"
        assert restored.is_offline_fallback is True
        assert restored.tool_call.arguments["app_name"] == "chrome"


class TestConversationTurn:
    def test_turn_creation(self):
        turn = ConversationTurn(user_input="Hello", agent_response="Greetings", timestamp=100.0)
        assert turn.user_input == "Hello"
        assert turn.agent_response == "Greetings"
        assert turn.timestamp == 100.0

    def test_turn_serialization(self):
        turn = ConversationTurn(user_input="Ping", agent_response="Pong")
        data = turn.to_dict()
        assert data["user_input"] == "Ping"
        restored = ConversationTurn.from_dict(data)
        assert restored.agent_response == "Pong"


class TestActiveContext:
    def test_context_state_tracking(self):
        ctx = ActiveContext()
        assert ctx.active_app is None
        assert ctx.history == []

        ctx.update_active_app("Google Chrome", "https://youtube.com")
        assert ctx.active_app == "Google Chrome"
        assert ctx.current_url == "https://youtube.com"

        ctx.active_subject = "Gate Smashers"
        ctx.add_turn("Open Chrome", "Opening Chrome now.")
        ctx.add_turn("Go to YouTube", "Navigating to YouTube.")

        assert len(ctx.history) == 2
        last = ctx.get_last_turn()
        assert last.user_input == "Go to YouTube"

        summary = ctx.format_history_for_prompt()
        assert "Open Chrome" in summary
        assert "Navigating to YouTube" in summary

    def test_clear_context(self):
        ctx = ActiveContext(active_app="Spotify", active_subject="music")
        ctx.add_turn("play", "playing")
        ctx.clear_context()

        assert ctx.active_app is None
        assert ctx.active_subject is None
        assert len(ctx.history) == 0

    def test_context_roundtrip_serialization(self):
        ctx = ActiveContext(active_app="Notepad", current_url=None)
        ctx.add_turn("write", "writing")
        data = ctx.to_dict()
        restored = ActiveContext.from_dict(data)
        assert restored.active_app == "Notepad"
        assert len(restored.history) == 1


class TestExecutionResult:
    def test_execution_result_defaults(self):
        res = ExecutionResult(success=True, output="Done")
        assert res.success is True
        assert res.verification_passed is True
        assert res.error_message is None

    def test_execution_result_failure(self):
        res = ExecutionResult(success=False, error_message="File not found", verification_passed=False)
        assert res.success is False
        assert res.verification_passed is False
        assert res.error_message == "File not found"


class TestNetworkStatus:
    def test_network_status_model(self):
        status = NetworkStatus(is_online=True, latency_ms=12.5)
        assert status.is_online is True
        assert status.latency_ms == 12.5
        assert status.target_host == "8.8.8.8"
        assert status.target_port == 53
