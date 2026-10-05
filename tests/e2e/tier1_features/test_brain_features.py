"""
Tier 1: Feature Coverage Tests for AI Brain & Context Engine (R2).
Covers:
- FEAT-BRAIN-001: Multilingual Intent Parser (5 tests)
- FEAT-BRAIN-002: Multi-Turn Context Tracker (5 tests)
- FEAT-BRAIN-003: Structured Decision Schema (5 tests)
- FEAT-BRAIN-004: Hybrid LLM & Offline Fallback (5 tests)
Total: 20 tests.
"""

import pytest
from tests.e2e.harness import BrainEngineAdapter, ActiveContext, RiskLevel, MockNetworkDetector


# ---------------------------------------------------------------------------
# FEAT-BRAIN-001: Multilingual Intent Parser
# ---------------------------------------------------------------------------

def test_feat_brain_001_english_open_chrome():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("Open Chrome")
    assert res["intent"] == "open_app"
    assert res["app"] == "Chrome"


def test_feat_brain_001_english_launch_browser():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("Launch the browser")
    assert res["intent"] == "open_app"
    assert res["app"] == "Chrome"


def test_feat_brain_001_hinglish_internet_chalana_hai():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("Internet chalana hai")
    assert res["intent"] == "open_app"
    assert res["app"] == "Chrome"


def test_feat_brain_001_hinglish_browser_kholo():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("Browser kholo")
    assert res["intent"] == "open_app"
    assert res["app"] == "Chrome"


def test_feat_brain_001_intent_parameter_extraction():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("Set volume to 85%")
    assert res["intent"] == "control_volume"
    assert res["level"] == 85


# ---------------------------------------------------------------------------
# FEAT-BRAIN-002: Multi-Turn Context Tracker
# ---------------------------------------------------------------------------

def test_feat_brain_002_context_retains_active_app():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    brain.process_input("Open Chrome", ctx)
    assert ctx.active_app == "Chrome"


def test_feat_brain_002_context_chains_navigation_to_active_app():
    brain = BrainEngineAdapter()
    ctx = ActiveContext(active_app="Chrome")
    decision = brain.process_input("Go to YouTube", ctx)
    assert ctx.current_url == "https://youtube.com"
    assert decision.tool_call.tool_name == "browser_navigate"


def test_feat_brain_002_context_chains_search_without_reprompting():
    brain = BrainEngineAdapter()
    ctx = ActiveContext(active_app="Chrome", current_url="https://youtube.com")
    decision = brain.process_input("Search Gate Smashers", ctx)
    assert decision.tool_call.tool_name == "youtube_search"
    assert "gate smashers" in decision.tool_call.arguments["query"]


def test_feat_brain_002_context_preserves_turn_history():
    ctx = ActiveContext()
    from tests.e2e.harness import ConversationTurn
    ctx.history.append(ConversationTurn(user_input="Hi", agent_response="Hello", timestamp=100.0))
    ctx.history.append(ConversationTurn(user_input="Help", agent_response="Sure", timestamp=101.0))
    assert len(ctx.history) == 2
    assert ctx.history[0].user_input == "Hi"


def test_feat_brain_002_context_overwrites_on_explicit_new_app():
    brain = BrainEngineAdapter()
    ctx = ActiveContext(active_app="Chrome")
    brain.process_input("Open Spotify", ctx)
    assert ctx.active_app == "Spotify"


# ---------------------------------------------------------------------------
# FEAT-BRAIN-003: Structured Decision Schema
# ---------------------------------------------------------------------------

def test_feat_brain_003_structured_reply_decision():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("What is the meaning of life?", ctx)
    assert dec.decision_type == "reply"
    assert dec.reply_text is not None


def test_feat_brain_003_structured_tool_call_decision():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("Open Chrome", ctx)
    assert dec.decision_type == "tool_call"
    assert dec.tool_call is not None
    assert dec.tool_call.tool_name == "open_app"


def test_feat_brain_003_structured_plan_decision():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("Kal COA exam hai, notes kholo aur syllabus check karo", ctx)
    assert dec.decision_type == "plan"
    assert dec.plan_goal is not None


def test_feat_brain_003_high_risk_decision_flags_confirmation():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("Delete all files in Downloads", ctx)
    assert dec.requires_confirmation is True
    assert dec.confirmation_prompt is not None


def test_feat_brain_003_schema_serializes_to_json():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("Open Chrome", ctx)
    json_data = dec.model_dump()
    assert "decision_type" in json_data
    assert "tool_call" in json_data


# ---------------------------------------------------------------------------
# FEAT-BRAIN-004: Hybrid LLM & Offline Fallback
# ---------------------------------------------------------------------------

def test_feat_brain_004_uses_cloud_model_when_online():
    net = MockNetworkDetector(online=True)
    brain = BrainEngineAdapter(network_detector=net)
    assert brain.is_online() is True
    assert brain.get_current_model() == "gemma4:cloud"


def test_feat_brain_004_falls_back_to_local_model_when_offline():
    net = MockNetworkDetector(online=False)
    brain = BrainEngineAdapter(network_detector=net)
    assert brain.is_online() is False
    assert brain.get_current_model() == "qwen2.5:7b"


def test_feat_brain_004_informs_user_on_offline_fallback():
    net = MockNetworkDetector(online=False)
    brain = BrainEngineAdapter(network_detector=net)
    ctx = ActiveContext()
    dec = brain.process_input("Open Chrome", ctx)
    assert "Offline mode activated" in dec.reply_text


def test_feat_brain_004_dynamic_transition_on_network_loss():
    net = MockNetworkDetector(online=True)
    brain = BrainEngineAdapter(network_detector=net)
    assert brain.get_current_model() == "gemma4:cloud"
    net.set_online(False)
    assert brain.get_current_model() == "qwen2.5:7b"


def test_feat_brain_004_dynamic_recovery_on_network_restore():
    net = MockNetworkDetector(online=False)
    brain = BrainEngineAdapter(network_detector=net)
    assert brain.get_current_model() == "qwen2.5:7b"
    net.set_online(True)
    assert brain.get_current_model() == "gemma4:cloud"
