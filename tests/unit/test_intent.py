"""
Unit tests for src/sam/brain/intent.py.
Verifies multilingual intent understanding, Hinglish idioms, context chaining,
destructive confirmation triggers, and protocol compliance.
"""

import pytest
from src.sam.brain.interface import IIntentParser
from src.sam.brain.intent import MultilingualIntentParser
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel


@pytest.fixture
def parser():
    return MultilingualIntentParser()


def test_intent_parser_implements_protocol(parser):
    """Verify MultilingualIntentParser implements IIntentParser protocol."""
    assert isinstance(parser, IIntentParser)


@pytest.mark.parametrize("phrase", [
    "Open Chrome",
    "Launch the browser",
    "Internet chalana hai",
    "Browser kholo",
])
def test_all_four_phrasings_open_chrome(parser, phrase):
    """Verify Acceptance Criteria line 50: all 4 phrasings result in Chrome opening."""
    decision = parser.parse(phrase)
    assert decision is not None
    assert decision.decision_type == "tool_call"
    assert decision.tool_call is not None
    assert decision.tool_call.tool_name == "open_app"
    assert decision.tool_call.arguments.get("app_name") == "chrome"
    assert decision.tool_call.risk_level == RiskLevel.LOW
    assert decision.requires_confirmation is False


def test_context_chaining_youtube_search(parser):
    """Verify Acceptance Criteria line 51: context-aware YouTube search without repeating context."""
    # Turn 1: Open Chrome
    turn1 = parser.parse("Open Chrome")
    assert turn1.tool_call.arguments["app_name"] == "chrome"

    # Context updated: Chrome active on YouTube
    context = ActiveContext(
        active_app="chrome",
        current_url="https://www.youtube.com",
        active_subject="YouTube",
    )

    # Turn 2: Search Gate Smashers
    turn2 = parser.parse("Search Gate Smashers", context=context)
    assert turn2 is not None
    assert turn2.decision_type == "tool_call"
    assert turn2.tool_call.tool_name == "search_youtube"
    assert "Gate Smashers" in turn2.tool_call.arguments["query"]


def test_destructive_command_triggers_high_risk_confirmation(parser):
    """Verify Acceptance Criteria line 72: delete commands trigger confirmation prompt."""
    decision = parser.parse("Delete all files in Downloads")
    assert decision is not None
    assert decision.decision_type == "tool_call"
    assert decision.tool_call.risk_level == RiskLevel.HIGH
    assert decision.requires_confirmation is True
    assert "Confirm" in decision.confirmation_prompt


def test_complex_goal_triggers_plan(parser):
    """Verify Acceptance Criteria line 68: complex multi-step goals produce plan."""
    phrase = "SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do"
    decision = parser.parse(phrase)
    assert decision is not None
    assert decision.decision_type == "plan"
    assert decision.plan_goal is not None


def test_spotify_intent(parser):
    """Verify music / Spotify launching intents."""
    decision = parser.parse("Open Spotify")
    assert decision is not None
    assert decision.tool_call.arguments["app_name"] == "spotify"

    decision_hinglish = parser.parse("Spotify chalao")
    assert decision_hinglish is not None
    assert decision_hinglish.tool_call.arguments["app_name"] == "spotify"


def test_volume_intents(parser):
    """Verify volume up and volume down intents."""
    up = parser.parse("Awaaz badhao")
    assert up is not None
    assert up.tool_call.tool_name == "control_volume"
    assert up.tool_call.arguments.get("delta") == 10

    down = parser.parse("Volume kam karo")
    assert down is not None
    assert down.tool_call.tool_name == "control_volume"
    assert down.tool_call.arguments.get("delta") == -10

    set_vol = parser.parse("Set volume to 85%")
    assert set_vol is not None
    assert set_vol.tool_call.arguments.get("level") == 85


def test_cpu_system_stats_intent(parser):
    """Verify CPU usage inquiry returns conversational reply."""
    decision = parser.parse("CPU usage check karo")
    assert decision is not None
    assert decision.decision_type == "reply"
    assert "CPU" in decision.reply_text
