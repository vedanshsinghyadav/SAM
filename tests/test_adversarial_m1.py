"""
Adversarial Stress Test Suite for Project SAM - Milestone 1.
Challenger: challenger_m1_1 (EMPIRICAL CHALLENGER)

Adversarially tests:
1. Intent Parsing: Casing, punctuation, Hinglish slang, greeting substring collisions ("hi").
2. Context Chaining: 15-turn rapid switches, cross-browser URL bleed, sliding window overflow.
3. Safety Boundaries: High-risk deletion variations, slang "uda do", directory parameter extraction.
4. Brain Integration: Pronoun chaining resolution through OllamaBrain.
5. Personality Engine: Witty metric invariants, tone adapter substring collisions ("hi", "hey").
"""

import pytest
from src.sam.brain.intent import MultilingualIntentParser
from src.sam.brain.context import ContextTracker
from src.sam.brain.ollama_client import OllamaBrain
from src.sam.personality.adapter import PersonalityAdapter
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel, ToolCall, ConversationTurn
from src.sam.common.network import set_forced_connectivity


# ============================================================================
# 1. Intent Parsing Stress Tests
# ============================================================================

class TestIntentAdversarialRobustness:

    @pytest.fixture
    def parser(self):
        return MultilingualIntentParser()

    @pytest.mark.parametrize("phrase", [
        "oPeN ChRoMe",
        "OPEN CHROME",
        "bRoWsEr KhOlO",
        "BROWSER KHOLO",
        "InTeRnEt ChAlAnA hAi",
        "INTERNET CHALANA HAI",
        "LaUnCh ThE bRoWsEr",
        "LAUNCH THE BROWSER",
        "   open   chrome   ",
        "open\tchrome",
        "open chrome!",
        "open chrome.",
        "Launch the browser!",
        "Browser kholo!",
        "Internet chalana hai...",
        "bhai internet chalao",
        "chrome khol de",
        "zara browser open karo",
        "chrome chalao na",
    ])
    def test_chrome_phrasings_casing_and_slang_success(self, parser, phrase):
        """Verify robust detection across mixed casing, punctuation, and known Hinglish idioms."""
        decision = parser.parse(phrase)
        assert decision is not None, f"Failed to parse phrasing: '{phrase}'"
        assert decision.decision_type == "tool_call"
        assert decision.tool_call.tool_name == "open_app"
        assert decision.tool_call.arguments.get("app_name") == "chrome"
        assert decision.tool_call.risk_level == RiskLevel.LOW
        assert decision.requires_confirmation is False

    @pytest.mark.parametrize("query", [
        "Delete this",
        "Close this",
        "Turn volume higher",
        "Show history",
        "Which app is open",
    ])
    def test_greeting_substring_collision_bug(self, parser, query):
        """
        FAILING TEST / DEFECT REPRODUCTION:
        In intent.py line 240:
          any(w in lower_text for w in ["hey sam", "hello", "hi", "kaise ho", "who are you"])
        Because 'w in lower_text' does raw substring matching instead of word boundary matching,
        the two letters 'hi' in 'this', 'higher', 'history', 'which' intercept the query
        and return a casual greeting reply instead of processing the command.
        """
        decision = parser.parse(query)
        # An unanchored greeting response here is a defect!
        if decision is not None and decision.decision_type == "reply":
            assert "At your service" not in decision.reply_text, (
                f"Query '{query}' was falsely hijacked by greeting match because it contains 'hi'!"
            )

    @pytest.mark.parametrize("slang_delete", [
        "Downloads k saare files uda do",
        "Downloads se saare files uda do",
    ])
    def test_dispatch_mandated_delete_slang_uda_do(self, parser, slang_delete):
        """
        FAILING TEST / DEFECT REPRODUCTION:
        Dispatch mandate: 'Downloads k saare files uda do' must strictly require confirmation.
        intent.py DELETE_PATTERNS only matches delete|mita|hata and ke saare,
        completely ignoring 'uda do' and single-character connector 'k saare'.
        """
        decision = parser.parse(slang_delete)
        assert decision is not None, f"Slang delete query '{slang_delete}' was ignored by intent parser!"
        assert decision.decision_type == "tool_call"
        assert decision.tool_call.tool_name == "delete_files"
        assert decision.tool_call.risk_level == RiskLevel.HIGH
        assert decision.requires_confirmation is True

    def test_directory_parameter_extraction_miscapture(self, parser):
        """
        FAILING TEST / DEFECT REPRODUCTION:
        In 'Downloads k files delete kar do', regex captures 'k' as directory instead of 'Downloads'.
        """
        decision = parser.parse("Downloads k files delete kar do")
        assert decision is not None
        assert decision.tool_call.arguments.get("directory") == "Downloads", (
            f"Extracted directory was '{decision.tool_call.arguments.get('directory')}', expected 'Downloads'!"
        )


# ============================================================================
# 2. Context Chaining Stress Tests
# ============================================================================

class TestContextChainingAdversarial:

    def test_cross_browser_url_bleed_over(self):
        """
        FAILING TEST / DEFECT REPRODUCTION:
        In context.py line 76:
          if self.context.active_app not in self.KNOWN_BROWSERS:
              self.context.current_url = None
        When switching between two different browsers (Chrome -> Edge or Edge -> Chrome),
        the current_url is NOT reset because both are in KNOWN_BROWSERS.
        This causes the active URL of one browser to bleed into the other.
        """
        tracker = ContextTracker()
        tracker.set_active_app("chrome")
        tracker.set_current_url("https://www.youtube.com")
        assert tracker.context.current_url == "https://www.youtube.com"

        # Switch to Edge
        tracker.set_active_app("edge")
        assert tracker.context.active_app == "edge"
        # Current URL must NOT bleed over from Chrome into Edge!
        assert tracker.context.current_url is None, (
            f"Chrome URL bled over into Edge: {tracker.context.current_url}"
        )

    def test_desktop_app_wipes_browser_url(self):
        """Verify non-browser application clears active browser URL."""
        tracker = ContextTracker()
        tracker.set_active_app("chrome")
        tracker.set_current_url("https://www.youtube.com")
        tracker.set_active_app("notepad")
        assert tracker.context.current_url is None

    def test_sliding_window_overflow_50_turns(self):
        """Stress test 50 turns with sliding window max 10."""
        tracker = ContextTracker(max_history_turns=10)
        for i in range(50):
            tracker.add_turn(f"User turn {i}", f"SAM response {i}")
        assert len(tracker.context.history) == 10
        assert tracker.context.history[0].user_input == "User turn 40"
        assert tracker.context.history[-1].user_input == "User turn 49"


# ============================================================================
# 3. Brain & Pronoun Chaining Integration
# ============================================================================

class TestBrainIntegrationAdversarial:

    def test_brain_pronoun_resolution_integration(self):
        """
        FAILING TEST / DEFECT REPRODUCTION:
        ContextTracker has resolve_chaining() which handles 'Close it'.
        However, OllamaBrain never calls resolve_chaining() in its processing pipeline.
        Calling brain.process_input('Close it', context) returns a generic reply,
        completely failing to close the active application.
        """
        brain = OllamaBrain(mock_mode=True)
        ctx = ActiveContext(active_app="chrome")

        decision = brain.process_input("Close it", ctx)
        assert decision.decision_type == "tool_call", (
            f"Expected tool_call 'close_app', but brain returned: {decision}"
        )
        assert decision.tool_call.tool_name == "close_app"
        assert decision.tool_call.arguments.get("app_name") == "chrome"

    def test_offline_failover_banner_and_model(self):
        """Verify offline mode triggers local model and prepends notice."""
        set_forced_connectivity(False)
        try:
            brain = OllamaBrain(mock_mode=True)
            assert brain.is_online() is False
            assert brain.get_current_model() == "qwen2.5:7b"

            dec = brain.process_input("Open Chrome", ActiveContext())
            assert dec.is_offline_fallback is True
            assert "[Notice: Offline mode active" in dec.reply_text
            assert dec.tool_call.tool_name == "open_app"
        finally:
            set_forced_connectivity(None)


# ============================================================================
# 4. Personality Adapter Tone Stress Tests
# ============================================================================

class TestPersonalityAdversarial:

    @pytest.fixture
    def adapter(self):
        return PersonalityAdapter()

    @pytest.mark.parametrize("phrase", [
        "The machine is running well",
        "This task finished successfully",
        "Check history please",
        "They are ready",
    ])
    def test_adapt_tone_substring_collision(self, adapter, phrase):
        """
        FAILING TEST / DEFECT REPRODUCTION:
        In adapter.py line 220:
          if 'hello' in lower or 'hi' in lower or 'hey' in lower:
              return 'Greetings! At your service.'
        Unanchored substring search for 'hi' and 'hey' replaces responses containing
        words like 'machine', 'this', 'history', 'they' with 'Greetings! At your service.'.
        """
        res = adapter.adapt_tone(phrase, is_task=False)
        assert res != "Greetings! At your service.", (
            f"Response '{phrase}' was corrupted by substring match into '{res}'!"
        )

    def test_cpu_wit_invariants(self, adapter):
        """Verify CPU metric query always includes wit across diverse percentages."""
        percentages = [5.2, 15, 45, 75, 95]
        for pct in percentages:
            res = adapter.format_system_metric("cpu", pct)
            assert res.strip() != f"{pct}%"
            assert any(w in res.lower() for w in ("cool", "sweat", "humming", "brisk", "silicon", "pulling", "fans"))
