"""
Personality Engine Interface Protocols and Enums for SAM.
Part of Milestone 1: FEAT-PERS-001, FEAT-PERS-002.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable


class ToneMode(str, Enum):
    CASUAL = "CASUAL"                # Helpful & mildly witty (JARVIS style small talk)
    TASK = "TASK"                    # Concise, professional, minimal tokens (task automation)
    SYSTEM_QUERY = "SYSTEM_QUERY"    # Informative hardware metrics with mild wit


class OutputModality(str, Enum):
    TEXT = "TEXT"                    # Terminal CLI, visual markdown
    VOICE = "VOICE"                  # Spoken audio via TTS (phonetically clean)


@runtime_checkable
class IPersonalityAdapter(Protocol):
    """Protocol for SAM's Personality & Tone Adaptation Engine."""

    def determine_tone_mode(
        self,
        decision_type: Optional[str] = None,
        tool_name: Optional[str] = None,
        has_active_task: bool = False,
        user_intent: Optional[str] = None
    ) -> ToneMode:
        """Determine whether to use CASUAL, TASK, or SYSTEM_QUERY tone."""
        ...

    def get_system_prompt_directive(self, mode: ToneMode) -> str:
        """Return the system prompt directive steering the LLM's persona for the given mode."""
        ...

    def format_system_metric(self, metric_name: str, value: Any, unit: str = "%") -> str:
        """Format raw system statistics (e.g. CPU, RAM, battery) with mild wit."""
        ...

    def adapt_task_response(
        self,
        action: str,
        target: Optional[str] = None,
        success: bool = True,
        details: Optional[str] = None
    ) -> str:
        """Format a task execution announcement or result concisely and professionally."""
        ...

    def sanitize_for_modality(self, text: str, modality: OutputModality = OutputModality.TEXT) -> str:
        """Sanitize text to guarantee phonetic clarity and modesty across spoken audio and CLI text."""
        ...
