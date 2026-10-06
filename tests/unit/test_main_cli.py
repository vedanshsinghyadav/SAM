"""
Unit tests for src/sam/main.py and src/sam/cli.py.
Validates SAMSystem lifecycle, turn orchestration, safety confirmation flows,
and CLI argument parsing.
Part of Milestone 7.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from src.sam.main import SAMSystem
from src.sam.cli import main as cli_main


class TestSAMMain(unittest.TestCase):
    """Validates SAMSystem orchestrator."""

    def setUp(self):
        self.sam = SAMSystem()

    def tearDown(self):
        self.sam.close()

    def test_sam_initializes_all_subsystems(self):
        self.assertIsNotNone(self.sam.brain)
        self.assertIsNotNone(self.sam.memory)
        self.assertIsNotNone(self.sam.controller)
        self.assertIsNotNone(self.sam.safety)
        self.assertIsNotNone(self.sam.vision)
        self.assertIsNotNone(self.sam.planner)
        self.assertIsNotNone(self.sam.voice)
        self.assertIsNotNone(self.sam.personality)

    def test_process_turn_reply(self):
        turn = self.sam.process_turn("Hello SAM")
        self.assertIn("styled_response", turn)
        self.assertFalse(turn["blocked"])
        self.assertGreater(len(turn["styled_response"]), 0)

    def test_process_turn_low_risk_tool(self):
        turn = self.sam.process_turn("Open Chrome")
        self.assertIn("styled_response", turn)
        self.assertFalse(turn["blocked"])

    def test_process_turn_high_risk_blocked_without_confirmation(self):
        turn = self.sam.process_turn("Delete all files in C:/temp")
        self.assertTrue(turn["blocked"])
        self.assertTrue(any(w in turn["styled_response"].lower() for w in ("sure", "confirm", "delete")))

    def test_process_turn_high_risk_allowed_with_confirmation(self):
        turn = self.sam.process_turn("Delete all files in C:/temp", user_confirmed=True)
        self.assertFalse(turn["blocked"])

    def test_voice_session_turn(self):
        wake_calls = []
        resp = self.sam.start_voice_session(
            on_wake_detected=lambda: wake_calls.append(True),
            mock_input="Hello"
        )
        self.assertEqual(len(wake_calls), 1)
        self.assertIsInstance(resp, str)
        self.assertGreater(len(resp), 0)


class TestSAMCLI(unittest.TestCase):
    """Validates CLI invocation."""

    @patch("src.sam.cli.SAMSystem")
    def test_cli_single_prompt(self, mock_sam_class):
        mock_instance = MagicMock()
        mock_instance.process_turn.return_value = {
            "styled_response": "Running tests for you."
        }
        mock_sam_class.return_value = mock_instance

        with patch("sys.argv", ["sam", "--prompt", "Run tests"]):
            cli_main()

        mock_instance.process_turn.assert_called_once_with("Run tests", user_confirmed=True)
        mock_instance.close.assert_called_once()

    @patch("src.sam.cli.SAMSystem")
    def test_cli_positional_prompt(self, mock_sam_class):
        mock_instance = MagicMock()
        mock_instance.process_turn.return_value = {
            "styled_response": "Chrome opened."
        }
        mock_sam_class.return_value = mock_instance

        with patch("sys.argv", ["sam", "open", "chrome"]):
            cli_main()

        mock_instance.process_turn.assert_called_once_with("open chrome", user_confirmed=True)
        mock_instance.close.assert_called_once()

    @patch("src.sam.cli.run_voice_mode")
    @patch("src.sam.cli.SAMSystem")
    def test_cli_positional_voice_mode(self, mock_sam_class, mock_run_voice):
        mock_instance = MagicMock()
        mock_sam_class.return_value = mock_instance

        with patch("sys.argv", ["sam", "voice"]):
            cli_main()

        mock_run_voice.assert_called_once_with(mock_instance)
        mock_instance.close.assert_called_once()
