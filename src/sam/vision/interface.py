"""
Vision Engine Interface and Protocol Definitions for Project SAM.
Conforms to PROJECT.md line 203 and E2E harness VisionAnalysis specifications.
Part of Milestone 4: FEAT-VIS-001, FEAT-VIS-002, FEAT-CTRL-004.
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple, runtime_checkable
from pydantic import Field

from src.sam.common.types import CompatibleBaseModel


class VisionAnalysis(CompatibleBaseModel):
    """Structured result of a desktop screen visual analysis."""
    extracted_text: str = Field(default="", description="Text extracted from screen OCR / vision model.")
    description: str = Field(default="", description="High-level description of visible window layout.")
    error_detected: bool = Field(default=False, description="Whether an active error dialog or crash is visible.")
    error_message: Optional[str] = Field(default=None, description="Extracted error message if error_detected is True.")


@runtime_checkable
class IVisionEngine(Protocol):
    """Contract interface for desktop screen vision and visual verification."""

    def capture_screen(
        self,
        output_path: Optional[str] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        monitor_index: Optional[int] = None
    ) -> str:
        """Capture screenshot to disk and return the file path."""
        ...

    def inspect_screen(
        self,
        query: str,
        image_path: Optional[str] = None
    ) -> VisionAnalysis:
        """Inspect current screen state or provided image using multimodal AI."""
        ...

    def verify_ui_state(
        self,
        expected_description: str,
        before_image: Optional[str] = None
    ) -> bool:
        """Verify whether screen matches expected post-action UI state."""
        ...

    def analyze_screen(
        self,
        prompt: str,
        image_path: Optional[str] = None
    ) -> str:
        """PROJECT.md protocol alias returning plain text analysis."""
        ...

    def verify_action_result(
        self,
        expected_outcome: str,
        before_image: Optional[str] = None
    ) -> bool:
        """PROJECT.md protocol alias for action verification."""
        ...
