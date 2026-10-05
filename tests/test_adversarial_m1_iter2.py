"""
Adversarial Iteration 2 Re-verification & Deep Edge-Case Harness.
Challenger: challenger_m1_iter2_1

Stress tests:
1. Word boundary precision in greeting patterns (Intent Parser & Tone Adapter)
   Testing tokens like "othello", "they", "whey", "fashion", "whitish", "adhik", etc.
2. Cross-browser transitions, synonyms, non-browser transitions, None transitions.
3. Hindi deletion slang variations, casing, spacing, and directory capture edge cases.
4. OllamaBrain mock and chaining pipeline under null/empty/active context states.
"""

import pytest
from src.sam.brain.intent import MultilingualIntentParser
from src.sam.brain.context import ContextTracker
from src.sam.brain.ollama_client import OllamaBrain
from src.sam.personality.adapter import PersonalityAdapter
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel, ToolCall


class TestGreetingWordBoundaryPrecision:

    @pytest.fixture
    def parser(self):
        return MultilingualIntentParser()

    @pytest.fixture
    def adapter(self):
        return PersonalityAdapter()

    @pytest.mark.parametrize("query,expected_not_greeting", [
        ("Delete this", True),
        ("Close this right now", True),
        ("Turn volume higher", True),
        ("Show history", True),
        ("Which app is open", True),
        ("Othello is a tragedy", True),
        ("They are ready", True),
        ("Whey protein shake", True),
        ("Fashion show tickets", True),
        ("The machine was repaired", True),
        ("Adhik jankari chahiye", True),
        ("White background", True),
        ("Shift to new window", True),
    ])
    def test_intent_parser_does_not_hijack_words_containing_hi_or_hey(self, parser, query, expected_not_greeting):
        decision = parser.parse(query)
        if decision and decision.decision_type == "reply":
            assert "At your service, sir. What shall we tackle today?" != decision.reply_text, (
                f"Query '{query}' was falsely treated as a casual greeting!"
            )

    @pytest.mark.parametrize("greeting", [
        "hi",
        "Hi",
        "HI",
        "hello",
        "Hello",
        "hey sam",
        "Hey Sam",
        "kaise ho",
        "Kaise Ho",
        "who are you",
    ])
    def test_intent_parser_recognizes_genuine_greetings(self, parser, greeting):
        decision = parser.parse(greeting)
        assert decision is not None, f"Greeting '{greeting}' was not recognized!"
        assert decision.decision_type == "reply"
        assert "At your service" in decision.reply_text

    @pytest.mark.parametrize("phrase", [
        "The machine is running well",
        "This task finished successfully",
        "Check history please",
        "They are ready",
        "Whey protein",
        "Othello plays",
        "Fashionable clothes",
        "Whitish color",
    ])
    def test_personality_adapter_preserves_non_greeting_words(self, adapter, phrase):
        result = adapter.adapt_tone(phrase, is_task=False)
        assert result != "Greetings! At your service.", (
            f"Phrase '{phrase}' was corrupted into greeting!"
        )

    @pytest.mark.parametrize("greeting_phrase", [
        "Hello",
        "hi",
        "hey",
        "Hey there!",
        "Hello world",
        "Well hi",
    ])
    def test_personality_adapter_adapts_genuine_greetings(self, adapter, greeting_phrase):
        result = adapter.adapt_tone(greeting_phrase, is_task=False)
        assert result == "Greetings! At your service."


class TestContextTrackerUrlTransitions:

    def test_cross_browser_isolation_chrome_to_edge(self):
        tracker = ContextTracker()
        tracker.set_active_app("chrome")
        tracker.set_current_url("https://github.com/project-sam")
        assert tracker.context.current_url == "https://github.com/project-sam"

        tracker.set_active_app("edge")
        assert tracker.context.active_app == "edge"
        assert tracker.context.current_url is None

    def test_cross_browser_isolation_edge_to_chrome(self):
        tracker = ContextTracker()
        tracker.set_active_app("edge")
        tracker.set_current_url("https://bing.com")
        assert tracker.context.current_url == "https://bing.com"

        tracker.set_active_app("chrome")
        assert tracker.context.active_app == "chrome"
        assert tracker.context.current_url is None

    def test_browser_synonym_preserves_url(self):
        tracker = ContextTracker()
        tracker.set_active_app("chrome")
        tracker.set_current_url("https://python.org")

        tracker.set_active_app("google chrome")
        assert tracker.context.active_app == "chrome"
        assert tracker.context.current_url == "https://python.org"

    def test_setting_none_app_clears_url(self):
        tracker = ContextTracker()
        tracker.set_active_app("chrome")
        tracker.set_current_url("https://python.org")

        tracker.set_active_app(None)
        assert tracker.context.active_app is None
        assert tracker.context.current_url is None

    def test_desktop_app_clears_url(self):
        tracker = ContextTracker()
        tracker.set_active_app("chrome")
        tracker.set_current_url("https://python.org")

        tracker.set_active_app("spotify")
        assert tracker.context.active_app == "spotify"
        assert tracker.context.current_url is None


class TestHindiSlangDeletionEdgeCases:

    @pytest.fixture
    def parser(self):
        return MultilingualIntentParser()

    @pytest.mark.parametrize("slang_cmd,expected_dir", [
        ("Downloads k saare files uda do", "Downloads"),
        ("Downloads se saare files uda do", "Downloads"),
        ("Downloads ke saare files uda do", "Downloads"),
        ("Downloads ki saari files uda do", "Downloads"),
        ("Downloads k files delete kar do", "Downloads"),
        ("Documents k saare files mita do", "Documents"),
        ("Desktop se files uda do", "Desktop"),
        ("uda do Downloads k saare files", "Downloads"),
        ("delete all files in Downloads", "Downloads"),
        ("clear all files in Temp", "Temp"),
        ("saare files uda do", "Downloads"),
        ("files uda do", "Downloads"),
    ])
    def test_hindi_slang_and_directory_target(self, parser, slang_cmd, expected_dir):
        decision = parser.parse(slang_cmd)
        assert decision is not None, f"Failed to parse slang delete: '{slang_cmd}'"
        assert decision.decision_type == "tool_call"
        assert decision.tool_call.tool_name == "delete_files"
        assert decision.tool_call.risk_level == RiskLevel.HIGH
        assert decision.requires_confirmation is True
        assert decision.tool_call.arguments.get("directory") == expected_dir
        assert decision.tool_call.arguments.get("path") == expected_dir


class TestOllamaBrainChainingRobustness:

    @pytest.fixture
    def brain(self):
        return OllamaBrain(mock_mode=True)

    @pytest.mark.parametrize("app_name", ["chrome", "edge", "spotify", "notepad"])
    def test_pronoun_closure_across_apps(self, brain, app_name):
        ctx = ActiveContext(active_app=app_name)
        decision = brain.process_input("Close it", ctx)
        assert decision.decision_type == "tool_call"
        assert decision.tool_call.tool_name == "close_app"
        assert decision.tool_call.arguments.get("app_name") == app_name

    def test_pronoun_closure_without_active_app(self, brain):
        ctx = ActiveContext(active_app=None)
        decision = brain.process_input("Close it", ctx)
        # Without an active app, chaining cannot resolve so it falls back gracefully
        assert decision.decision_type == "reply"

    def test_youtube_search_chaining_via_brain(self, brain):
        ctx = ActiveContext(active_app="chrome", current_url="https://www.youtube.com")
        decision = brain.process_input("Search Gate Smashers", ctx)
        assert decision.decision_type == "tool_call"
        assert decision.tool_call.tool_name == "search_youtube"
        assert decision.tool_call.arguments.get("query") == "Gate Smashers"
