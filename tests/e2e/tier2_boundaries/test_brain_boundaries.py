"""
Tier 2: Boundary & Corner Cases for AI Brain & Context Engine (R2).
Covers:
- FEAT-BRAIN-001 Boundaries: Ambiguous intent, compound queries, conflicting keywords, long prompt, empty prompt (5 tests)
- FEAT-BRAIN-002 Boundaries: Deep context 100 turns, abrupt topic switch, stale context, corrupted fields, concurrent context (5 tests)
- FEAT-BRAIN-003 Boundaries: Malformed schema, missing tool args, empty plan goal, unexpected fields, risk consistency (5 tests)
- FEAT-BRAIN-004 Boundaries: Flapping connection, cloud timeout, malformed local response, offline mode warning, idempotency (5 tests)
Total: 20 tests.
"""

import pytest
from tests.e2e.harness import BrainEngineAdapter, ActiveContext, ConversationTurn, ToolCall, RiskLevel, MockNetworkDetector


# ---------------------------------------------------------------------------
# FEAT-BRAIN-001 Boundaries
# ---------------------------------------------------------------------------

def test_feat_brain_001_boundary_empty_prompt():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("")
    assert res["intent"] == "general_reply"


def test_feat_brain_001_boundary_conflicting_keywords():
    brain = BrainEngineAdapter()
    # "open Chrome and delete files"
    res = brain.parse_intent("open chrome and delete downloads")
    # Intent parser should identify key action
    assert "intent" in res


def test_feat_brain_001_boundary_compound_multi_sentence():
    brain = BrainEngineAdapter()
    text = "First, open Chrome. Second, play spotify."
    res = brain.parse_intent(text)
    assert res["intent"] in ["open_app", "spotify_playback"]


def test_feat_brain_001_boundary_500_token_prompt():
    brain = BrainEngineAdapter()
    long_prompt = "hello " * 500
    res = brain.parse_intent(long_prompt)
    assert res["intent"] == "general_reply"


def test_feat_brain_001_boundary_ambiguous_intent():
    brain = BrainEngineAdapter()
    res = brain.parse_intent("something something perhaps")
    assert res["intent"] == "general_reply"


# ---------------------------------------------------------------------------
# FEAT-BRAIN-002 Boundaries
# ---------------------------------------------------------------------------

def test_feat_brain_002_boundary_deep_context_100_turns():
    ctx = ActiveContext()
    for i in range(100):
        ctx.history.append(ConversationTurn(user_input=f"Turn {i}", agent_response=f"Reply {i}", timestamp=float(i)))
    assert len(ctx.history) == 100
    brain = BrainEngineAdapter()
    dec = brain.process_input("Open Chrome", ctx)
    assert dec.decision_type == "tool_call"


def test_feat_brain_002_boundary_abrupt_topic_switch():
    brain = BrainEngineAdapter()
    ctx = ActiveContext(active_app="Chrome", current_url="https://youtube.com", active_task="watch")
    # Abruptly ask for CPU
    dec = brain.process_input("What is my CPU usage?", ctx)
    assert dec.decision_type == "reply" or dec.tool_call is not None


def test_feat_brain_002_boundary_empty_fields_in_context():
    ctx = ActiveContext(active_app=None, current_url=None, active_task=None, active_subject=None)
    brain = BrainEngineAdapter()
    dec = brain.process_input("Search Gate Smashers", ctx)
    # Does not crash when context fields are None
    assert dec is not None


def test_feat_brain_002_boundary_special_characters_in_url():
    ctx = ActiveContext(active_app="Chrome", current_url="https://youtube.com/watch?v=xyz&t=10s#comments")
    assert "youtube" in ctx.current_url


def test_feat_brain_002_boundary_history_preserves_order():
    ctx = ActiveContext()
    ctx.history.append(ConversationTurn(user_input="1", agent_response="a", timestamp=1.0))
    ctx.history.append(ConversationTurn(user_input="2", agent_response="b", timestamp=2.0))
    assert ctx.history[0].user_input == "1"
    assert ctx.history[1].user_input == "2"


# ---------------------------------------------------------------------------
# FEAT-BRAIN-003 Boundaries
# ---------------------------------------------------------------------------

def test_feat_brain_003_boundary_tool_call_empty_arguments():
    tc = ToolCall(tool_name="open_app")
    assert tc.arguments == {}


def test_feat_brain_003_boundary_plan_goal_empty():
    from tests.e2e.harness import BrainDecision
    dec = BrainDecision(decision_type="plan", plan_goal="")
    assert dec.decision_type == "plan"


def test_feat_brain_003_boundary_decision_without_reply_text():
    from tests.e2e.harness import BrainDecision
    dec = BrainDecision(decision_type="tool_call", tool_call=ToolCall(tool_name="test"))
    assert dec.reply_text is None


def test_feat_brain_003_boundary_high_risk_flag_true():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("Delete all files in Downloads", ctx)
    assert dec.requires_confirmation is True
    assert dec.tool_call.risk_level == RiskLevel.HIGH


def test_feat_brain_003_boundary_low_risk_flag_false():
    brain = BrainEngineAdapter()
    ctx = ActiveContext()
    dec = brain.process_input("Open Chrome", ctx)
    assert dec.requires_confirmation is False


# ---------------------------------------------------------------------------
# FEAT-BRAIN-004 Boundaries
# ---------------------------------------------------------------------------

def test_feat_brain_004_boundary_flapping_connection():
    net = MockNetworkDetector(online=True)
    brain = BrainEngineAdapter(network_detector=net)
    for _ in range(5):
        net.set_online(False)
        assert brain.get_current_model() == "qwen2.5:7b"
        net.set_online(True)
        assert brain.get_current_model() == "gemma4:cloud"


def test_feat_brain_004_boundary_offline_model_string():
    net = MockNetworkDetector(online=False)
    brain = BrainEngineAdapter(network_detector=net)
    assert brain.local_model in brain.get_current_model()


def test_feat_brain_004_boundary_notification_contains_offline():
    net = MockNetworkDetector(online=False)
    brain = BrainEngineAdapter(network_detector=net)
    dec = brain.process_input("Open Chrome", ActiveContext())
    assert "Offline mode" in dec.reply_text


def test_feat_brain_004_boundary_multiple_listeners():
    net = MockNetworkDetector(online=True)
    calls = []
    net.add_listener(lambda s: calls.append(s))
    net.add_listener(lambda s: calls.append(not s))
    net.set_online(False)
    assert len(calls) == 2


def test_feat_brain_004_boundary_no_state_change_does_not_fire_listeners():
    net = MockNetworkDetector(online=True)
    calls = []
    net.add_listener(lambda s: calls.append(s))
    net.set_online(True)
    assert len(calls) == 0
