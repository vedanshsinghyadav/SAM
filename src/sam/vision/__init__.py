"""
SAM Vision Engine Subsystem.
Provides desktop screen capture, multimodal AI screen understanding, and visual action verification.
Part of Milestone 4: FEAT-VIS-001, FEAT-VIS-002, FEAT-CTRL-004.
"""

from src.sam.vision.analyzer import VisionAnalyzer
from src.sam.vision.capture import ScreenCaptureEngine
from src.sam.vision.client import MultimodalVisionClient, encode_image_to_base64
from src.sam.vision.engine import VisionEngine
from src.sam.vision.interface import (
    IVisionEngine,
    VisionAnalysis,
)

__all__ = [
    "IVisionEngine",
    "VisionAnalysis",
    "ScreenCaptureEngine",
    "MultimodalVisionClient",
    "VisionAnalyzer",
    "VisionEngine",
    "encode_image_to_base64",
]
