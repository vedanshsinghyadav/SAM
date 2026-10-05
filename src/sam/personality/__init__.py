"""
SAM Personality Module: Adaptive Dual-Tone and Modality Invariance.
"""

from src.sam.personality.interface import IPersonalityAdapter, OutputModality, ToneMode
from src.sam.personality.adapter import PersonalityAdapter

__all__ = [
    "ToneMode",
    "OutputModality",
    "IPersonalityAdapter",
    "PersonalityAdapter",
]
