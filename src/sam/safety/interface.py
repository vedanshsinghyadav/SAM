"""
Interface definitions and protocols for SAM Safety and Permission Guard.
Strictly conforms to PROJECT.md lines 210-224 and M3 specifications.
"""

from __future__ import annotations
from typing import List, Protocol, Tuple, runtime_checkable
from src.sam.common.types import ToolCall, RiskLevel


@runtime_checkable
class ISafetyGuard(Protocol):
    """
    Protocol for the Tri-Tier Safety Guard and Authorization Engine.
    Enforces risk categorization:
    - LOW: Immediate execution (no announcement, no confirmation)
    - MEDIUM: Pre-execution announcement logged and communicated
    - HIGH: Mandatory blocking confirmation barrier (requires explicit user confirmation)
    """

    announcements: List[str]

    def classify_risk(self, tool_call: ToolCall) -> RiskLevel:
        """Classify tool risk level into LOW, MEDIUM, or HIGH."""
        ...

    def authorize(self, tool_call: ToolCall, user_confirmed: bool = False) -> Tuple[bool, str]:
        """Verify whether an action is authorized to execute.

        Returns (is_authorized, reason_or_prompt).
        """
        ...

    def generate_confirmation_prompt(self, tool_call: ToolCall) -> str:
        """Generate structured prompt detailing targets to be affected by high-risk action."""
        ...

    def is_affirmative_confirmation(self, user_response: str) -> bool:
        """Determine if natural language user input constitutes affirmative confirmation."""
        ...
