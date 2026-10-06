"""
SAM Safety and Permission Guard Subsystem.
Exports SafetyGuard and ISafetyGuard protocol.
"""

from src.sam.safety.interface import ISafetyGuard
from src.sam.safety.guard import SafetyGuard

__all__ = [
    "ISafetyGuard",
    "SafetyGuard",
]
