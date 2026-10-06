"""
Unit tests for src/sam/voice/ subsystem.
Validates IVoiceInterface protocol, wake word detection (<2.0s),
STT transcription, TTS synthesis, and barge-in interruption (<1.0s).
Part of Milestone 6: R1 (FEAT-VOICE-001 through FEAT-VOICE-005).
"""

import time
import unittest
import pytest

from src.sam.voice.interface import IVoiceInterface
from src.sam.voice.wake_word import WakeWordDetector
from src.sam.voice.stt import SpeechToTextEngine
from src.sam.voice.tts import TextToSpeechEngine
from src.sam.voice.interruption import BargeInHandler
from src.sam.voice.engine import VoiceEngine


class TestVoiceInterfaceProtocol(unittest.TestCase):
    """Validates structural protocol conformance."""

    def test_implements_protocol(self):
        engine = VoiceEngine()
        self.assertIsInstance(engine, IVoiceInterface)


class TestWakeWordDetector(unittest.TestCase):
    """Validates wake word detection and latency."""

    def setUp(self):
        self.detector = WakeWordDetector()

    def test_is_wake_word(self):
        self.assertTrue(self.detector.is_wake_word("Hey SAM, open Chrome"))
        self.assertTrue(self.detector.is_wake_word("SAM what time is it?"))
        self.assertTrue(self.detector.is_wake_word("sam"))
        self.assertFalse(self.detector.is_wake_word("Hello computer"))
        self.assertFalse(self.detector.is_wake_word(""))

    def test_trigger_latency_under_2_seconds(self):
        events = []
        latency = self.detector.trigger(lambda: events.append("triggered"))
        self.assertEqual(len(events), 1)
        self.assertLess(latency, 2.0)

    def test_trigger_propagates_callback_exception(self):
        def failing_cb():
            raise RuntimeError("Callback crashed")

        with self.assertRaises(RuntimeError):
            self.detector.trigger(failing_cb)


class TestSpeechToTextEngine(unittest.TestCase):
    """Validates speech transcription behavior and boundaries."""

    def setUp(self):
        self.stt = SpeechToTextEngine()

    def test_transcribe_english(self):
        result = self.stt.transcribe(mock_audio_text="Open Chrome")
        self.assertEqual(result, "Open Chrome")

    def test_transcribe_hinglish(self):
        result = self.stt.transcribe(mock_audio_text="Internet chalana hai")
        self.assertEqual(result, "Internet chalana hai")

    def test_transcribe_punctuation_and_casing(self):
        text = "SAM, where are my COA notes?"
        self.assertEqual(self.stt.transcribe(mock_audio_text=text), text)

    def test_transcribe_technical_terms(self):
        text = "Run script.py with powershell"
        self.assertEqual(self.stt.transcribe(mock_audio_text=text), text)

    def test_transcribe_silence_and_whitespace(self):
        self.assertEqual(self.stt.transcribe(mock_audio_text=""), "")
        self.assertEqual(self.stt.transcribe(mock_audio_text="   \t\n   "), "")

    def test_transcribe_maximum_length(self):
        long_text = "word " * 500
        result = self.stt.transcribe(mock_audio_text=long_text)
        self.assertEqual(len(result.split()), 500)


class TestTextToSpeechEngine(unittest.TestCase):
    """Validates audio synthesis and playback lifecycle."""

    def setUp(self):
        self.tts = TextToSpeechEngine()

    def test_speak_lifecycle(self):
        self.assertFalse(self.tts.is_speaking)
        self.tts.speak("Opening Chrome for you.")
        self.assertTrue(self.tts.is_speaking)
        self.assertEqual(self.tts.last_spoken_text, "Opening Chrome for you.")
        self.assertGreater(self.tts.speech_start_time, 0.0)

        self.tts.stop()
        self.assertFalse(self.tts.is_speaking)

    def test_speak_emojis_and_symbols(self):
        text = "Task completed! 🚀 100% success."
        self.tts.speak(text)
        self.assertEqual(self.tts.last_spoken_text, text)

    def test_speak_large_text(self):
        giant = "A" * 10000
        self.tts.speak(giant)
        self.assertEqual(len(self.tts.last_spoken_text), 10000)


class TestBargeInHandler(unittest.TestCase):
    """Validates audio interruption detection and latency."""

    def setUp(self):
        self.handler = BargeInHandler()

    def test_is_interrupt_phrase(self):
        self.assertTrue(self.handler.is_interrupt_phrase("stop"))
        self.assertTrue(self.handler.is_interrupt_phrase("SAM stop"))
        self.assertTrue(self.handler.is_interrupt_phrase("Please stop now"))
        self.assertTrue(self.handler.is_interrupt_phrase("sAm StOp"))
        self.assertFalse(self.handler.is_interrupt_phrase("continue playing"))
        self.assertFalse(self.handler.is_interrupt_phrase(""))

    def test_handle_barge_in_latency_under_1_second(self):
        halted = []
        interrupted, latency = self.handler.handle_barge_in("SAM stop", lambda: halted.append(True))
        self.assertTrue(interrupted)
        self.assertEqual(len(halted), 1)
        self.assertLess(latency, 1.0)


class TestVoiceEngine(unittest.TestCase):
    """Validates full VoiceEngine integration."""

    def setUp(self):
        self.voice = VoiceEngine()

    def test_start_listening(self):
        fired = []
        self.voice.start_listening(lambda: fired.append(True))
        self.assertTrue(self.voice.is_listening)
        self.assertEqual(len(fired), 1)

    def test_listen_utterance(self):
        res = self.voice.listen_utterance("Launch Spotify")
        self.assertTrue(self.voice.is_listening)
        self.assertEqual(res, "Launch Spotify")

    def test_speak_and_barge_in(self):
        self.voice.speak("This is an explanation of quantum physics...")
        self.assertTrue(self.voice.is_speaking)
        self.assertFalse(self.voice.interrupted)

        latency = self.voice.simulate_barge_in("SAM stop")
        self.assertLess(latency, 1.0)
        self.assertFalse(self.voice.is_speaking)
        self.assertTrue(self.voice.interrupted)

    def test_barge_in_ignored_for_non_stop(self):
        self.voice.speak("Reading file contents...")
        latency = self.voice.simulate_barge_in("carry on please")
        self.assertLess(latency, 1.0)
        self.assertTrue(self.voice.is_speaking)
        self.assertFalse(self.voice.interrupted)

    def test_new_speech_resets_interrupted(self):
        self.voice.speak("First statement.")
        self.voice.simulate_barge_in("stop")
        self.assertTrue(self.voice.interrupted)

        self.voice.speak("Second statement.")
        self.assertFalse(self.voice.interrupted)
