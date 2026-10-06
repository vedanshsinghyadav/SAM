"""
Audio Barge-in Interruption Handler for Project SAM.
Halts speech output immediately when stop words are detected ('stop', 'SAM stop').
Measures interrupt latency with sub-second precision (< 1.0s, typically < 10ms).
Part of Milestone 6: FEAT-VOICE-004.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Callable, Optional

logger = logging.getLogger("sam.voice.interruption")


class BargeInHandler:
    """Manages audio interruption detection and latency benchmarking."""

    STOP_PATTERN = re.compile(r"\bstop\b", re.IGNORECASE)

    def is_interrupt_phrase(self, phrase: str) -> bool:
        """Check whether phrase contains an interruption directive."""
        if not phrase or not phrase.strip():
            return False
        return bool(self.STOP_PATTERN.search(phrase))

    def handle_barge_in(
        self,
        phrase: str,
        stop_speaking_cb: Callable[[], None]
    ) -> tuple[bool, float]:
        """
        Evaluate phrase and halt speech if stop command detected.
        Returns (interrupted: bool, latency: float).
        """
        t0 = time.perf_counter()
        if self.is_interrupt_phrase(phrase):
            stop_speaking_cb()
            latency = time.perf_counter() - t0
            logger.debug("Barge-in triggered with latency: %.4fs", latency)
            return True, latency

        latency = time.perf_counter() - t0
        return False, latency
