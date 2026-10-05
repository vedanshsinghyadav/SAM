"""
Interface contracts and protocols for SAM AI Brain Engine.
Directly implements interface specifications in PROJECT.md lines 160-178.
"""

from typing import Optional, Protocol, runtime_checkable
from src.sam.common.types import ActiveContext, BrainDecision


@runtime_checkable
class IBrain(Protocol):
    """Core cognitive interface for reasoning and decision formulation."""

    def process_input(self, user_text: str, context: ActiveContext) -> BrainDecision:
        """Process user natural language input within conversational context.

        Args:
            user_text: The user's input string (English, Hindi, or Hinglish).
            context: Active session context including active app, url, task,
                     subject, and turn history.

        Returns:
            BrainDecision: Validated structured decision ('reply', 'tool_call', or 'plan').
        """
        ...

    def is_online(self) -> bool:
        """Check whether online connectivity is currently active.

        Returns:
            bool: True if network is connected to cloud backend, False otherwise.
        """
        ...

    def get_current_model(self) -> str:
        """Return the identifier of the currently active LLM backend.

        Returns:
            str: Model name (e.g. 'gemma4:cloud' or 'qwen2.5:7b').
        """
        ...


@runtime_checkable
class IIntentParser(Protocol):
    """Protocol for intent normalization and semantic classification."""

    def parse(self, user_text: str, context: Optional[ActiveContext] = None) -> Optional[BrainDecision]:
        """Parse natural language query and resolve to a candidate structured decision.

        Args:
            user_text: Raw input query.
            context: Optional active context for coreference and ellipsis resolution.

        Returns:
            Optional[BrainDecision]: Extracted structured candidate decision, or None.
        """
        ...
