"""
Unit tests for src/sam/brain/context.py.
Validates multi-turn context tracking, context chaining across turns,
pronoun resolution, sliding window history pruning, and serialization.
"""

import unittest
from src.sam.brain.context import ContextTracker, ChainingResolution
from src.sam.common.types import ActiveContext, ConversationTurn


class TestContextTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = ContextTracker(max_history_turns=5)

    def test_context_initialization_defaults(self):
        ctx = self.tracker.context
        self.assertIsNone(ctx.active_app)
        self.assertIsNone(ctx.current_url)
        self.assertIsNone(ctx.active_task)
        self.assertIsNone(ctx.active_subject)
        self.assertEqual(len(ctx.history), 0)

    def test_turn_history_recording(self):
        self.tracker.add_turn("Open Chrome", "Opening Google Chrome.")
        self.assertEqual(len(self.tracker.context.history), 1)
        turn = self.tracker.context.history[0]
        self.assertEqual(turn.user_input, "Open Chrome")
        self.assertEqual(turn.agent_response, "Opening Google Chrome.")
        self.assertGreater(turn.timestamp, 0)

    def test_sliding_window_pruning(self):
        # max_history_turns is 5
        for i in range(8):
            self.tracker.add_turn(f"User {i}", f"SAM {i}")
        self.assertEqual(len(self.tracker.context.history), 5)
        self.assertEqual(self.tracker.context.history[0].user_input, "User 3")
        self.assertEqual(self.tracker.context.history[-1].user_input, "User 7")

    def test_active_app_normalization(self):
        self.tracker.set_active_app("Google Chrome")
        self.assertEqual(self.tracker.context.active_app, "chrome")

        self.tracker.set_active_app("Microsoft Edge")
        self.assertEqual(self.tracker.context.active_app, "edge")

        self.tracker.set_active_app("Spotify")
        self.assertEqual(self.tracker.context.active_app, "spotify")

    def test_url_tracking_auto_browser_binding(self):
        self.tracker.set_current_url("https://www.youtube.com")
        self.assertEqual(self.tracker.context.active_app, "chrome")
        self.assertEqual(self.tracker.context.current_url, "https://www.youtube.com")

        # Switching to desktop app resets current_url
        self.tracker.set_active_app("Notepad")
        self.assertEqual(self.tracker.context.active_app, "notepad")
        self.assertIsNone(self.tracker.context.current_url)

    def test_context_chaining_chrome_youtube_search(self):
        """
        Direct verification of Acceptance Criteria line 51:
        'Open Chrome' -> 'Go to YouTube' -> 'Search Gate Smashers'
        """
        # Step 1: Open Chrome
        self.tracker.set_active_app("chrome")
        self.assertEqual(self.tracker.context.active_app, "chrome")

        # Step 2: Go to YouTube
        res2 = self.tracker.resolve_chaining("Go to YouTube")
        self.assertTrue(res2.resolved)
        self.assertEqual(res2.inferred_action, "navigate_url")
        self.assertEqual(res2.inferred_app, "chrome")
        self.assertEqual(res2.inferred_url, "https://www.youtube.com")

        # Apply state
        self.tracker.set_current_url(res2.inferred_url)

        # Step 3: Search Gate Smashers
        res3 = self.tracker.resolve_chaining("Search Gate Smashers")
        self.assertTrue(res3.resolved)
        self.assertEqual(res3.inferred_action, "search_youtube")
        self.assertEqual(res3.inferred_app, "chrome")
        self.assertEqual(res3.search_query, "Gate Smashers")
        self.assertIn("youtube.com/results?search_query=Gate+Smashers", res3.parameters["search_url"])

    def test_pronoun_anaphora_resolution(self):
        self.tracker.set_active_app("chrome")
        res = self.tracker.resolve_chaining("Close it")
        self.assertTrue(res.resolved)
        self.assertEqual(res.inferred_action, "close_app")
        self.assertEqual(res.parameters["app_name"], "chrome")

        self.tracker.set_active_subject("lecture1.pdf")
        res2 = self.tracker.resolve_chaining("Move it to COA")
        self.assertTrue(res2.resolved)
        self.assertEqual(res2.inferred_action, "file_action")
        self.assertEqual(res2.inferred_subject, "lecture1.pdf")

    def test_update_from_decision(self):
        self.tracker.update_from_decision("tool_call", "open_app", {"app_name": "chrome"})
        self.assertEqual(self.tracker.context.active_app, "chrome")

        self.tracker.update_from_decision("tool_call", "open_url", {"url": "https://github.com"})
        self.assertEqual(self.tracker.context.current_url, "https://github.com")

        self.tracker.update_from_decision("tool_call", "search_youtube", {"query": "tutorial"})
        self.assertEqual(self.tracker.context.active_subject, "tutorial")
        self.assertEqual(self.tracker.context.active_task, "search")

        self.tracker.update_from_decision("tool_call", "close_app", {"app_name": "chrome"})
        self.assertIsNone(self.tracker.context.active_app)
        self.assertIsNone(self.tracker.context.current_url)

    def test_serialization_roundtrip(self):
        self.tracker.set_active_app("chrome")
        self.tracker.set_current_url("https://github.com")
        self.tracker.set_active_subject("sam-repo")
        self.tracker.add_turn("Open GitHub", "Opened GitHub.")

        data = self.tracker.to_dict()
        restored = ContextTracker.from_dict(data)

        self.assertEqual(restored.context.active_app, "chrome")
        self.assertEqual(restored.context.current_url, "https://github.com")
        self.assertEqual(restored.context.active_subject, "sam-repo")
        self.assertEqual(len(restored.context.history), 1)


if __name__ == "__main__":
    unittest.main()
