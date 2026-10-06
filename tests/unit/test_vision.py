"""
Unit tests for SAM Vision Engine (Milestone 4).
Tests:
- IVisionEngine protocol compliance
- Screen capture file creation, region clipping, directory auto-creation
- Multimodal client parsing, error detection, heuristic fallback
- Visual action verifier UI matching and error overrides
- Base64 image encoding utilities
"""

import os
import tempfile
import pytest

from src.sam.vision.capture import ScreenCaptureEngine, MINIMAL_VALID_PNG
from src.sam.vision.client import MultimodalVisionClient, encode_image_to_base64
from src.sam.vision.engine import VisionEngine
from src.sam.vision.interface import IVisionEngine, VisionAnalysis


class TestVisionProtocol:
    """Verifies interface contract conformance."""

    def test_implements_ivision_engine_protocol(self):
        engine = VisionEngine()
        assert isinstance(engine, IVisionEngine)

    def test_protocol_aliases(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Visual Studio Code active")
        text = engine.analyze_screen("Query")
        assert "Visual Studio Code" in text
        assert engine.verify_action_result("Visual Studio Code") is True


class TestScreenCaptureEngine:
    """Tests screenshot generation and directory handling."""

    def test_capture_creates_valid_png(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            path = capture.capture()
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
            with open(path, "rb") as f:
                header = f.read(8)
                assert header == b"\x89PNG\r\n\x1a\n"

    def test_capture_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = os.path.join(tmp_dir, "nested", "deeply", "screen.png")
            capture = ScreenCaptureEngine()
            result = capture.capture(output_path=target)
            assert os.path.exists(result)
            assert os.path.exists(target)

    def test_capture_with_region(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            path = capture.capture(region=(0, 0, 100, 100))
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0


class TestMultimodalVisionClient:
    """Tests multimodal parsing and error detection heuristics."""

    def test_parse_normal_screen_text(self):
        client = MultimodalVisionClient()
        text, has_err, err_msg = client._parse_vision_response("Desktop Workspace showing Chrome and Spotify")
        assert has_err is False
        assert err_msg is None
        assert "Chrome" in text

    def test_parse_error_screen_text(self):
        client = MultimodalVisionClient()
        raw = "Fatal Error: [Errno 2] No such file or directory: 'notes.txt'"
        text, has_err, err_msg = client._parse_vision_response(raw)
        assert has_err is True
        assert err_msg is not None
        assert "Fatal Error" in err_msg

    def test_parse_hindi_error_keyword(self):
        client = MultimodalVisionClient()
        raw = "सिस्टम त्रुटि: कनेक्शन विफल रहा"
        text, has_err, err_msg = client._parse_vision_response(raw)
        assert has_err is True
        assert "त्रुटि" in err_msg

    def test_base64_encoding_utility(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(MINIMAL_VALID_PNG)
            temp_path = f.name
        try:
            b64 = encode_image_to_base64(temp_path)
            assert b64 is not None
            assert len(b64) > 0
            # Test nonexistent file
            assert encode_image_to_base64("nonexistent_image_123.png") is None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestVisionEngine:
    """Tests unified VisionEngine inspection and verification."""

    def test_inspect_screen_normal_state(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Desktop Workspace - Normal operation")
        analysis = engine.inspect_screen("Describe screen")
        assert isinstance(analysis, VisionAnalysis)
        assert analysis.error_detected is False
        assert "Desktop" in analysis.extracted_text

    def test_inspect_screen_error_detection(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Error 404: Not Found", error_detected=True, error_message="Error 404: Not Found")
        analysis = engine.inspect_screen("What does this error say?")
        assert analysis.error_detected is True
        assert "Error 404: Not Found" in analysis.extracted_text
        assert analysis.error_message == "Error 404: Not Found"

    def test_verify_ui_state_success(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Google Chrome - New Tab")
        assert engine.verify_ui_state("Google Chrome") is True
        assert engine.verify_ui_state("New Tab") is True

    def test_verify_ui_state_empty_passes(self):
        engine = VisionEngine()
        assert engine.verify_ui_state("") is True

    def test_verify_ui_state_blocked_on_error(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Exception in thread main", error_detected=True)
        assert engine.verify_ui_state("Calculator") is False
