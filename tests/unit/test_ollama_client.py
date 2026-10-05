"""
Unit tests for src/sam/brain/ollama_client.py.
Verifies hybrid cloud/local failover, offline notification, markdown JSON extraction,
resilient mock mode, and IBrain protocol compliance.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.sam.brain.interface import IBrain
from src.sam.brain.ollama_client import OllamaBrain
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel


def test_ollama_brain_implements_ibrain_protocol():
    """Verify OllamaBrain conforms to IBrain protocol via runtime check."""
    brain = OllamaBrain(mock_mode=True)
    assert isinstance(brain, IBrain)


def test_online_default_uses_cloud_model():
    """Verify default model is gemma4:cloud when online."""
    brain = OllamaBrain(
        cloud_model="gemma4:cloud",
        local_model="qwen2.5:7b",
        network_checker=lambda: True,
        mock_mode=True,
    )
    assert brain.is_online() is True
    brain.process_input("Open Chrome", ActiveContext())
    assert brain.get_current_model() == "gemma4:cloud"


def test_offline_triggers_local_model_and_informs_user():
    """Verify Acceptance Criteria line 52: offline triggers qwen2.5:7b and informs user."""
    brain = OllamaBrain(
        cloud_model="gemma4:cloud",
        local_model="qwen2.5:7b",
        network_checker=lambda: False,
        mock_mode=True,
    )
    assert brain.is_online() is False
    decision = brain.process_input("Browser kholo", ActiveContext())
    assert brain.get_current_model() == "qwen2.5:7b"
    assert "[Notice: Offline mode active" in decision.reply_text
    assert decision.tool_call.arguments["app_name"] == "chrome"
    assert decision.is_offline_fallback is True


def test_cloud_error_fails_over_to_local_model():
    """Verify cloud network/HTTP error automatically triggers fallback to local model."""
    brain = OllamaBrain(
        cloud_model="gemma4:cloud",
        local_model="qwen2.5:7b",
        network_checker=lambda: True,
        mock_mode=False,
    )

    call_count = 0
    def mock_call(user_text, context, model_name):
        nonlocal call_count
        call_count += 1
        if model_name == "gemma4:cloud":
            raise RuntimeError("Cloud endpoint timeout")
        return '{"decision_type": "reply", "reply_text": "Local response"}'

    with patch.object(brain, "_call_ollama", side_effect=mock_call):
        decision = brain.process_input("Hello", ActiveContext())
        assert brain.get_current_model() == "qwen2.5:7b"
        assert "[Notice: Offline mode active" in decision.reply_text
        assert "Local response" in decision.reply_text
        assert call_count == 2
        assert decision.is_offline_fallback is True


def test_json_parsing_with_markdown_fences():
    """Verify JSON extractor correctly parses markdown code blocks."""
    brain = OllamaBrain(mock_mode=False)
    raw = (
        "```json\n"
        '{\n  "decision_type": "tool_call",\n  "reply_text": "Opening",\n'
        '  "tool_call": {"tool_name": "open_app", "arguments": {"app_name": "chrome"}, "risk_level": "LOW"},\n'
        '  "requires_confirmation": false\n}\n'
        "```"
    )
    decision = brain._parse_json_decision(raw)
    assert decision.decision_type == "tool_call"
    assert decision.tool_call.tool_name == "open_app"


def test_json_parsing_with_outermost_braces():
    """Verify JSON extractor handles surrounding commentary outside braces."""
    brain = OllamaBrain(mock_mode=False)
    raw = 'Here is your structured decision: {"decision_type": "reply", "reply_text": "Hello, sir."} Hope that helps!'
    decision = brain._parse_json_decision(raw)
    assert decision.decision_type == "reply"
    assert decision.reply_text == "Hello, sir."


def test_malformed_json_fallback():
    """Verify malformed JSON falls back gracefully to intent parser without crashing."""
    brain = OllamaBrain(mock_mode=False)
    raw = "Not a valid JSON payload at all"
    decision = brain._parse_json_decision(raw)
    assert isinstance(decision, BrainDecision)
