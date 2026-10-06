"""
Voice Interface Subsystem for Project SAM.
Exports VoiceEngine, IVoiceInterface, and supporting voice components.
"""

from src.sam.voice.engine import VoiceEngine
from src.sam.voice.interface import IVoiceInterface
from src.sam.voice.interruption import BargeInHandler
from src.sam.voice.stt import SpeechToTextEngine
from src.sam.voice.tts import TextToSpeechEngine
from src.sam.voice.wake_word import WakeWordDetector

__all__ = [
    "VoiceEngine",
    "IVoiceInterface",
    "WakeWordDetector",
    "SpeechToTextEngine",
    "TextToSpeechEngine",
    "BargeInHandler",
]
