"""
Voice Interface Protocol for Project SAM.
Defines IVoiceInterface for wake word detection, speech-to-text (STT),
text-to-speech (TTS), and audio barge-in interruption.
Part of Milestone 6: R1 (FEAT-VOICE-001 through FEAT-VOICE-005).
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class IVoiceInterface(Protocol):
    """Protocol defining the conversational voice subsystem."""

    is_listening: bool
    is_speaking: bool
    last_spoken_text: str
    interrupted: bool
    speech_start_time: float
    interrupt_latency: float

    def start_listening(self, wake_word_callback: Callable[[], None]) -> None:
        """
        Activate always-listening loop and invoke callback upon detecting wake word ('Hey SAM').
        Must activate within 2.0s.
        """
        ...

    def listen_utterance(self, mock_audio_text: str = "Open Chrome") -> str:
        """
        Record and transcribe user spoken audio to text.
        Supports Hindi/Hinglish, technical terms, and punctuation.
        """
        ...

    def speak(self, text: str, on_interrupt: Optional[Callable[[], None]] = None) -> None:
        """
        Synthesize text to spoken audio.
        Non-blocking or interruptible via barge-in.
        """
        ...

    def simulate_barge_in(self, interrupt_phrase: str = "SAM stop") -> float:
        """
        Halt audio output upon user interrupt phrase ('stop', 'SAM stop').
        Returns measured latency in seconds (must be < 1.0s).
        """
        ...

    def stop_speaking(self) -> None:
        """Immediately silence audio synthesis."""
        ...
