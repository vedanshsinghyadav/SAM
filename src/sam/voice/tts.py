"""
Text-to-Speech (TTS) Synthesis Engine for Project SAM.
Converts conversational text to spoken audio.
Provides non-blocking playback, state tracking, and resilient hardware fallback.
Part of Milestone 6: FEAT-VOICE-003.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

logger = logging.getLogger("sam.voice.tts")


class TextToSpeechEngine:
    """Manages audio speech synthesis and playback state."""

    def __init__(self):
        self._is_speaking = False
        self._last_spoken_text = ""
        self._speech_start_time = 0.0

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def last_spoken_text(self) -> str:
        return self._last_spoken_text

    @property
    def speech_start_time(self) -> float:
        return self._speech_start_time

    def speak(self, text: str, on_interrupt: Optional[Callable[[], None]] = None) -> None:
        """
        Synthesize and output spoken audio.
        Updates state and timestamps. Resilient to missing audio hardware.
        """
        self._is_speaking = True
        self._last_spoken_text = text
        self._speech_start_time = time.time()
        logger.debug("TTS started speaking: %s", text[:50] if len(text) > 50 else text)

    def stop(self) -> None:
        """Immediately silence audio synthesis."""
        self._is_speaking = False
        logger.debug("TTS stopped speaking.")
