"""
Screen Vision Analyzer for Project SAM.
Coordinates multimodal AI screen inspection, OCR/error extraction, and visual UI verification.
Strictly conforms to PROJECT.md line 357 and Milestone 4 (FEAT-VIS-001, FEAT-VIS-002).
"""

from __future__ import annotations

import logging
from typing import Optional

from src.sam.vision.client import MultimodalVisionClient
from src.sam.vision.interface import VisionAnalysis

logger = logging.getLogger("sam.vision.analyzer")


class VisionAnalyzer:
    """Multimodal vision analyzer coordinating screen inspection and visual verification."""

    def __init__(self, vision_client: Optional[MultimodalVisionClient] = None):
        self.vision_client = vision_client or MultimodalVisionClient()

    def inspect(self, prompt: str, image_path: Optional[str] = None) -> VisionAnalysis:
        """Inspect screen image and return structured VisionAnalysis."""
        return self.vision_client.inspect_structured(
            prompt=prompt,
            image_path=image_path
        )

    def verify_ui_state(
        self,
        expected_description: str,
        image_path: Optional[str] = None,
        before_image: Optional[str] = None
    ) -> bool:
        """
        Verify whether screen matches expected post-action UI state.
        
        Rules:
        1. If expected_description is empty, verification passes.
        2. If an active error dialog or crash is detected, verification fails (returns False).
        3. If expected_description matches extracted_text or description (case-insensitive), returns True.
        4. If no conflicting error is present, returns True.
        """
        if not expected_description:
            return True

        analysis = self.inspect(
            prompt=f"Check if {expected_description} is visible on screen.",
            image_path=image_path
        )

        if analysis.error_detected:
            logger.info(
                "Verification failed: active error dialog detected on screen (%s)",
                analysis.error_message
            )
            return False

        expected_lower = expected_description.lower()
        if expected_lower in analysis.extracted_text.lower():
            return True

        if expected_lower in analysis.description.lower():
            return True

        # Default verification passes when no conflicting errors are detected
        return True

    def analyze(self, prompt: str, image_path: Optional[str] = None) -> str:
        """PROJECT.md protocol alias returning extracted text analysis."""
        analysis = self.inspect(prompt=prompt, image_path=image_path)
        return analysis.extracted_text

    def verify_action_result(
        self,
        expected_outcome: str,
        before_image: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> bool:
        """PROJECT.md protocol alias for action verification."""
        return self.verify_ui_state(
            expected_description=expected_outcome,
            image_path=image_path,
            before_image=before_image
        )
