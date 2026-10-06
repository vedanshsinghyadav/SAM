"""
Unit tests for SAM GUI application (src/sam/gui/app.py).
Validates UI initialization, command dispatch, confirmation flow,
and clean termination.
"""

import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from src.sam.gui.app import SAMGuiApp


class TestSAMGuiApp(unittest.TestCase):
    """Validates SAM Desktop GUI lifecycle."""

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.app = SAMGuiApp(self.root)
        except tk.TclError:
            self.skipTest("Tkinter display not available in headless test environment")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app.entry_var = None
            self.app._on_close()
        elif hasattr(self, "root"):
            self.root.destroy()

    def test_gui_initializes_with_status_ready(self):
        self.assertIn("Ready", self.app.status_label.cget("text"))
        self.assertFalse(self.app.is_processing)
        self.assertFalse(self.app.voice_running)

    def test_gui_sends_user_command_asynchronously(self):
        self.app.entry_var.set("Hello SAM")
        with patch.object(self.app.sam, "process_turn", return_value={"styled_response": "Hello!"}) as mock_turn:
            self.app._on_send_click()
            self.assertTrue(self.app.is_processing)
            # Drain queue / wait briefly for background thread
            import time
            time.sleep(0.1)
            self.app._process_queue()
            self.assertFalse(self.app.is_processing)
            mock_turn.assert_called_once()

    def test_gui_handles_blocked_confirmation(self):
        turn_blocked = {
            "blocked": True,
            "response_text": "Confirm deletion of files?"
        }
        with patch.object(self.app.sam, "process_turn", return_value=turn_blocked):
            self.app._dispatch_command("delete files")
            import time
            time.sleep(0.1)
            self.app._process_queue()
            self.assertEqual(self.app.pending_confirmation, "delete files")
            self.assertIn("Confirm", self.app.confirm_label.cget("text"))

            # Cancel confirmation
            self.app._cancel_confirmed_action()
            self.assertIsNone(self.app.pending_confirmation)

    def test_gui_voice_toggle(self):
        self.assertFalse(self.app.voice_running)
        self.app._toggle_voice_mode()
        self.assertTrue(self.app.voice_running)
        self.app._toggle_voice_mode()
        self.assertFalse(self.app.voice_running)
