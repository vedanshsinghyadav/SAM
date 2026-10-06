"""
Comprehensive Unit Tests for SAM Vision Subsystem (Milestone 4).
Tests:
- IVisionEngine protocol conformance and schema serialization
- Screen capture engine: mss, Pillow, PowerShell, minimal PNG fallbacks
- Absolute path guarantees, directory creation, region normalization
- Multi-monitor detection and indexing (monitor_index)
- Temporary screenshot lifecycle and retention cleanup
- Multimodal vision client: FreeLLMAPI, Ollama cascade, circuit breaker, structured JSON
- VisionAnalyzer: screen QA, visual UI verification, error override
- Unified VisionEngine: coordination, simulation hooks, protocol aliases
- Boundary & stress cases: dense text, unicode, special characters
"""

import io
import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from src.sam.vision.analyzer import VisionAnalyzer
from src.sam.vision.capture import ScreenCaptureEngine, MINIMAL_VALID_PNG
from src.sam.vision.client import (
    MultimodalVisionClient,
    encode_image_to_base64,
    VISION_SYSTEM_PROMPT,
)
from src.sam.vision.engine import VisionEngine
from src.sam.vision.interface import IVisionEngine, VisionAnalysis


# ============================================================================
# 1. Interface & Protocol Tests
# ============================================================================

class TestVisionProtocolAndInterface:
    """Verifies interface contract conformance and schema validation."""

    def test_implements_ivision_engine_protocol(self):
        engine = VisionEngine()
        assert isinstance(engine, IVisionEngine)

    def test_protocol_aliases(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Visual Studio Code active")
        text = engine.analyze_screen("Query")
        assert "Visual Studio Code" in text
        assert engine.verify_action_result("Visual Studio Code") is True

    def test_vision_analysis_schema_defaults_and_serialization(self):
        va = VisionAnalysis()
        assert va.extracted_text == ""
        assert va.description == ""
        assert va.error_detected is False
        assert va.error_message is None

        # Test dictionary serialization across Pydantic compatibility layer
        d = va.to_dict()
        assert isinstance(d, dict)
        assert d["error_detected"] is False

        # Custom populated model
        custom = VisionAnalysis(
            extracted_text="Error: Connection Refused",
            description="System error dialog",
            error_detected=True,
            error_message="Error: Connection Refused"
        )
        assert custom.error_detected is True
        assert custom.error_message == "Error: Connection Refused"
        dumped = custom.model_dump()
        assert dumped["extracted_text"] == "Error: Connection Refused"


# ============================================================================
# 2. Screen Capture Engine Tests
# ============================================================================

class TestScreenCaptureEngine:
    """Tests screenshot generation, multi-monitor, fallbacks, and storage management."""

    def test_capture_creates_valid_png(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            path = capture.capture()
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
            with open(path, "rb") as f:
                header = f.read(8)
                assert header == b"\x89PNG\r\n\x1a\n"

    def test_capture_guarantees_absolute_path_default_and_custom(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            p1 = capture.capture()
            assert os.path.isabs(p1)

            # Custom relative path must be converted to absolute path
            rel_custom = os.path.join(".", "test_relative_shot.png")
            p2 = capture.capture(output_path=rel_custom)
            try:
                assert os.path.isabs(p2)
                assert os.path.exists(p2)
            finally:
                if os.path.exists(p2):
                    os.remove(p2)

    def test_capture_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = os.path.join(tmp_dir, "nested", "deeply", "screen.png")
            capture = ScreenCaptureEngine()
            result = capture.capture(output_path=target)
            assert os.path.exists(result)
            assert os.path.exists(target)
            assert os.path.isabs(result)

    def test_capture_with_valid_region(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            path = capture.capture(region=(0, 0, 100, 100))
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_capture_with_inverted_or_zero_region(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            # Inverted coordinates (100, 100) -> (50, 50)
            path = capture.capture(region=(100, 100, 50, 50))
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_get_monitors_returns_metadata(self):
        capture = ScreenCaptureEngine()
        monitors = capture.get_monitors()
        assert isinstance(monitors, list)
        assert len(monitors) > 0
        primary = monitors[0]
        assert "width" in primary
        assert "height" in primary

    def test_capture_with_monitor_index(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            path = capture.capture(monitor_index=0)
            assert os.path.exists(path)
            assert os.path.isabs(path)

    def test_temp_capture_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            captured_path = None
            with capture.temp_capture() as path:
                captured_path = path
                assert os.path.exists(captured_path)
                assert os.path.isabs(captured_path)

            # Auto-deleted on context manager exit
            assert not os.path.exists(captured_path)

    def test_cleanup_old_captures_pruning(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            # Create 5 dummy capture files
            created_files = []
            for i in range(5):
                fpath = os.path.join(tmp_dir, f"screen_capture_{1000 + i}.png")
                with open(fpath, "wb") as f:
                    f.write(MINIMAL_VALID_PNG)
                created_files.append(fpath)

            # Prune to keep at most 2 files
            removed = capture.cleanup_old_captures(max_age_seconds=86400, max_files=2)
            assert removed == 3
            remaining = [f for f in created_files if os.path.exists(f)]
            assert len(remaining) == 2

    def test_fallback_to_minimal_png_when_engines_fail(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture = ScreenCaptureEngine(default_output_dir=tmp_dir)
            with patch.object(capture, "_try_mss_capture", return_value=False), \
                 patch.object(capture, "_try_pillow_capture", return_value=False), \
                 patch.object(capture, "_try_powershell_capture", return_value=False):
                path = capture.capture()
                assert os.path.exists(path)
                with open(path, "rb") as f:
                    assert f.read() == MINIMAL_VALID_PNG


# ============================================================================
# 3. Multimodal Vision Client Tests
# ============================================================================

class TestMultimodalVisionClient:
    """Tests multimodal parsing, circuit breaker, Ollama cascade, and heuristic fallbacks."""

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
            assert encode_image_to_base64("nonexistent_image_123.png") is None
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_json_response_parsing_valid_json(self):
        client = MultimodalVisionClient()
        payload = json.dumps({
            "extracted_text": "Error 404: Not Found",
            "description": "Browser showing 404 error page",
            "error_detected": True,
            "error_message": "Error 404: Not Found"
        })
        analysis = client._parse_json_vision_response(payload)
        assert isinstance(analysis, VisionAnalysis)
        assert analysis.error_detected is True
        assert analysis.error_message == "Error 404: Not Found"
        assert "404" in analysis.extracted_text

    def test_json_response_parsing_markdown_fences(self):
        client = MultimodalVisionClient()
        raw = """```json
{
  "extracted_text": "VS Code - main.py",
  "description": "Code editor window active",
  "error_detected": false,
  "error_message": null
}
```"""
        analysis = client._parse_json_vision_response(raw)
        assert analysis.error_detected is False
        assert "VS Code" in analysis.extracted_text
        assert "Code editor" in analysis.description

    def test_json_response_parsing_malformed_falls_back_heuristics(self):
        client = MultimodalVisionClient()
        raw = "Some unformatted model prose. Fatal Error: Memory allocation failure!"
        analysis = client._parse_json_vision_response(raw)
        assert analysis.error_detected is True
        assert "Fatal Error" in analysis.error_message

    def test_freellmapi_success_mock(self):
        client = MultimodalVisionClient()
        mock_response_body = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "extracted_text": "Terminal window",
                        "description": "Powershell prompt",
                        "error_detected": False,
                        "error_message": None
                    })
                }
            }]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = mock_response_body
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            analysis = client.inspect_structured("Describe screen")
            assert analysis.extracted_text == "Terminal window"
            assert analysis.error_detected is False

    def test_freellmapi_rate_limit_429_activates_cooldown(self):
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        http_err = urllib.error.HTTPError(
            url="http://127.0.0.1:31415",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b'{"error": "rate_limited"}')
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            # First call triggers 429 and updates failure timestamp
            analysis1 = client.inspect_structured("Describe screen")
            assert client._last_freellm_failure > 0
            # Clean fallback to heuristics
            assert "Desktop" in analysis1.extracted_text

        # Second call within cooldown skips FreeLLMAPI without making network calls
        with patch.object(client, "_query_freellmapi") as mock_q:
            analysis2 = client.inspect_structured("Describe screen")
            mock_q.assert_not_called()
            assert "Desktop" in analysis2.extracted_text

    def test_ollama_cascade_success_mock(self):
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        # Force FreeLLMAPI into cooldown
        client._last_freellm_failure = time.time()

        mock_ollama_resp = json.dumps({
            "response": json.dumps({
                "extracted_text": "Ollama vision text",
                "description": "Ollama description",
                "error_detected": False,
                "error_message": None
            })
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = mock_ollama_resp
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            analysis = client.inspect_structured("Describe screen")
            assert analysis.extracted_text == "Ollama vision text"

    def test_backward_compatible_inspect_tuple(self):
        client = MultimodalVisionClient()
        text, has_err, err_msg = client.inspect("Describe screen")
        assert isinstance(text, str)
        assert isinstance(has_err, bool)
        assert err_msg is None or isinstance(err_msg, str)


# ============================================================================
# 4. Vision Analyzer Tests
# ============================================================================

class TestVisionAnalyzer:
    """Tests VisionAnalyzer screen inspection and visual UI verification."""

    def test_analyzer_inspect_delegates_to_client(self):
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="Notepad - sample.txt",
            description="Text editor",
            error_detected=False
        )
        analyzer = VisionAnalyzer(vision_client=mock_client)
        analysis = analyzer.inspect("Check text", image_path="shot.png")
        assert analysis.extracted_text == "Notepad - sample.txt"
        mock_client.inspect_structured.assert_called_once_with(
            prompt="Check text",
            image_path="shot.png"
        )

    def test_analyzer_verify_ui_state_empty_description(self):
        analyzer = VisionAnalyzer()
        assert analyzer.verify_ui_state("") is True

    def test_analyzer_verify_ui_state_matching_extracted_text(self):
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="Google Chrome - New Tab",
            description="Browser window",
            error_detected=False
        )
        analyzer = VisionAnalyzer(vision_client=mock_client)
        assert analyzer.verify_ui_state("Google Chrome") is True
        assert analyzer.verify_ui_state("new tab") is True

    def test_analyzer_verify_ui_state_fails_on_active_error(self):
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="Fatal Exception in module kernel",
            description="Crash dialog",
            error_detected=True,
            error_message="Fatal Exception"
        )
        analyzer = VisionAnalyzer(vision_client=mock_client)
        assert analyzer.verify_ui_state("Google Chrome") is False

    def test_analyzer_protocol_aliases(self):
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="Calculator window",
            description="Calculator",
            error_detected=False
        )
        analyzer = VisionAnalyzer(vision_client=mock_client)
        assert analyzer.analyze("Prompt") == "Calculator window"
        assert analyzer.verify_action_result("Calculator") is True


# ============================================================================
# 5. Unified Vision Engine Tests
# ============================================================================

class TestVisionEngine:
    """Tests unified VisionEngine coordination and mock simulation hooks."""

    def test_engine_dependency_injection(self):
        capture_mock = MagicMock()
        capture_mock.capture.return_value = "/abs/path/mock.png"
        client_mock = MagicMock()
        analyzer_mock = MagicMock()

        engine = VisionEngine(
            capture_engine=capture_mock,
            vision_client=client_mock,
            analyzer=analyzer_mock
        )
        assert engine.capture_screen() == "/abs/path/mock.png"
        capture_mock.capture.assert_called_once()

    def test_set_mock_screen_state_and_clear(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Mock Window", error_detected=False)
        analysis1 = engine.inspect_screen("Describe")
        assert analysis1.extracted_text == "Mock Window"

        engine.clear_mock_screen_state()
        assert engine._mock_mode is False
        assert engine.mock_screen_text == ""

    def test_inspect_screen_with_injected_error(self):
        engine = VisionEngine()
        engine.set_mock_screen_state(
            "Error 500: Internal Server Error",
            error_detected=True,
            error_message="Error 500"
        )
        analysis = engine.inspect_screen("What is the error?")
        assert analysis.error_detected is True
        assert analysis.error_message == "Error 500"

    def test_verify_ui_state_exact_match(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Spotify Premium Active")
        assert engine.verify_ui_state("Spotify Premium Active") is True

    def test_verify_ui_state_case_insensitive(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("SPOTIFY PREMIUM ACTIVE")
        assert engine.verify_ui_state("spotify") is True

    def test_verify_ui_state_empty_criteria_passes(self):
        engine = VisionEngine()
        assert engine.verify_ui_state("") is True

    def test_verify_ui_state_blocked_by_active_error(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Kernel Panic Error", error_detected=True)
        assert engine.verify_ui_state("Notepad") is False


# ============================================================================
# 6. Edge Cases and Resilience Tests
# ============================================================================

class TestVisionEdgeCasesAndResilience:
    """Tests edge cases: dense text, special characters, unicode, and queries."""

    def test_dense_text_screen_inspection(self):
        engine = VisionEngine()
        dense_text = " ".join([f"token_{i}" for i in range(500)])
        engine.set_mock_screen_state(dense_text)
        analysis = engine.inspect_screen("Read dense text")
        assert "token_499" in analysis.extracted_text

    def test_empty_query_string_handling(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("Default Desktop Workspace")
        analysis = engine.inspect_screen("")
        assert analysis is not None
        assert isinstance(analysis.extracted_text, str)

    def test_special_characters_in_ui_verification(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("File [C:\\Program Files\\App] - v1.0 (64-bit)")
        assert engine.verify_ui_state("[C:\\Program Files\\App]") is True

    def test_unicode_and_hinglish_queries(self):
        engine = VisionEngine()
        engine.set_mock_screen_state("त्रुटि: फ़ाइल नहीं मिली (FileNotFoundError)")
        analysis = engine.inspect_screen("screen par kya likha hai")
        assert "त्रुटि" in analysis.extracted_text
