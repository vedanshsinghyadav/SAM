"""
Adversarial Stress Test Suite for Project SAM - Milestone 4 (Vision Subsystem).
Challenger: challenger_m4_2 (EMPIRICAL CHALLENGER)

Adversarially tests:
1. Malformed and corrupted LLM outputs:
   - Truncated JSON, missing keys, markdown wrapping variations, pure garbage/HTML,
     null values, type mismatch coercion, and graceful heuristic recovery.
2. Network timeout and circuit breaker stress:
   - HTTP 429 rate limits, socket timeouts, connection refused, 500 errors.
   - Rapid tripping, strict <50ms fast-fail verification under cooldown, and cooldown recovery.
3. UI error text edge cases:
   - Subtle error keywords (Traceback, Exception, SyntaxError, Failed, Hindi 'त्रुटि', 'विफल').
   - Case-insensitivity, secondary error detection override, expected description matching.
4. Multithreaded concurrency stress under load:
   - 30-50 concurrent workers under circuit breaker tripping, analyzer verification,
     and simultaneous screen capture file generation.
5. Multilingual intent parsing in src/sam/brain/intent.py:
   - Screen inspection queries in English & Hinglish, false positive rejection,
     and specific dispatch target phrases ('screen par kya dikh raha hai', 'is there an error on screen').
"""

import concurrent.futures
import io
import json
import os
import tempfile
import time
from typing import Optional
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from src.sam.brain.intent import MultilingualIntentParser
from src.sam.common.types import RiskLevel
from src.sam.vision.analyzer import VisionAnalyzer
from src.sam.vision.capture import ScreenCaptureEngine, MINIMAL_VALID_PNG
from src.sam.vision.client import (
    MultimodalVisionClient,
    ERROR_KEYWORDS,
)
from src.sam.vision.engine import VisionEngine
from src.sam.vision.interface import VisionAnalysis


# ============================================================================
# 1. Malformed & Corrupted LLM Output Stress Tests
# ============================================================================

class TestAdversarialMalformedLLMOutput:
    """Stress tests LLM response parser against hostile, corrupted, and non-standard outputs."""

    @pytest.fixture
    def client(self):
        return MultimodalVisionClient()

    def test_markdown_wrapped_json_variations(self, client):
        """Markdown codeblocks with various notations, spacing, and prose wrapping."""
        cases = [
            # Standard markdown json
            '```json\n{"extracted_text": "Error: File missing", "description": "Dialog", "error_detected": true, "error_message": "File missing"}\n```',
            # Generic code fence
            '```\n{"extracted_text": "Normal screen", "description": "Desktop", "error_detected": false, "error_message": null}\n```',
            # Preamble and postamble conversational text
            'Here is your JSON analysis:\n```json\n{"extracted_text": "Workspace", "description": "IDE", "error_detected": false, "error_message": null}\n```\nHope that helps!',
            # Extra newlines and spaces inside fence
            '  ```json  \n\n  {"extracted_text": "Terminal", "description": "Shell", "error_detected": false, "error_message": null}  \n  ```  ',
        ]
        for c in cases:
            analysis = client._parse_json_vision_response(c)
            assert isinstance(analysis, VisionAnalysis)
            assert isinstance(analysis.extracted_text, str)
            assert isinstance(analysis.description, str)
            assert isinstance(analysis.error_detected, bool)

    def test_missing_keys_graceful_defaults(self, client):
        """JSON objects missing some or all required keys."""
        cases = [
            # Completely empty dict
            "{}",
            # Only extracted_text
            '{"extracted_text": "Only some text visible"}',
            # Only description
            '{"description": "Only a description here"}',
            # Only error_detected without error_message
            '{"error_detected": true}',
            # Only error_message
            '{"error_message": "Something went wrong"}',
            # Partial dict
            '{"extracted_text": "Hi", "error_detected": false}',
        ]
        for c in cases:
            analysis = client._parse_json_vision_response(c)
            assert isinstance(analysis, VisionAnalysis)
            assert analysis.extracted_text is not None
            assert analysis.description is not None
            assert isinstance(analysis.error_detected, bool)

    def test_truncated_json_heuristic_recovery(self, client):
        """Truncated JSON streams due to max_tokens exhaustion."""
        cases = [
            # Truncated midway through extracted_text with an error
            '{"extracted_text": "Fatal Exception: out of memory in worker',
            # Truncated inside keys
            '{"extracted_text": "Normal operational window", "desc',
            # Truncated after key
            '{"extracted_text": "Error: Null pointer", "error_detected": ',
            # Only opening brace
            '{',
            # Opening brace with quote
            '{"',
        ]
        for c in cases:
            analysis = client._parse_json_vision_response(c)
            assert isinstance(analysis, VisionAnalysis)
            assert isinstance(analysis.extracted_text, str)
            assert isinstance(analysis.description, str)
            # If the truncated text contained an error keyword, verify heuristic detected it
            if "exception" in c.lower() or "error" in c.lower():
                assert analysis.error_detected is True

    def test_pure_garbage_and_non_json(self, client):
        """Hostile non-JSON payloads: HTML, whitespace, emojis, binary noise."""
        cases = [
            "",
            "   \n\t   ",
            "<!DOCTYPE html><html><body>502 Bad Gateway - Nginx</body></html>",
            "!@#$%^&*()_+{}[]:;\"'<>?,./~`1234567890",
            "🎉🚀🔥💻 Windows Desktop with ⚠️ alert",
            "Just pure conversational rambling without any JSON formatting whatsoever.",
            "A" * 5000,  # 5KB continuous token stream
        ]
        for c in cases:
            analysis = client._parse_json_vision_response(c)
            assert isinstance(analysis, VisionAnalysis)
            assert isinstance(analysis.extracted_text, str)
            assert isinstance(analysis.description, str)
            assert isinstance(analysis.error_detected, bool)

    def test_type_corrupted_fields(self, client):
        """Fields containing unexpected data types (ints, lists, dicts, nulls)."""
        payload = json.dumps({
            "extracted_text": 12345,
            "description": ["Window 1", "Window 2"],
            "error_detected": "true",
            "error_message": 999
        })
        analysis = client._parse_json_vision_response(payload)
        assert isinstance(analysis, VisionAnalysis)
        assert analysis.extracted_text == "12345"
        assert "Window 1" in analysis.description
        assert analysis.error_detected is True
        assert analysis.error_message == "999"

    def test_explicit_null_fields(self, client):
        """JSON payload with all values explicitly set to null."""
        payload = json.dumps({
            "extracted_text": None,
            "description": None,
            "error_detected": None,
            "error_message": None
        })
        analysis = client._parse_json_vision_response(payload)
        assert isinstance(analysis, VisionAnalysis)
        # Verify no crash occurs and fields are populated cleanly
        assert analysis.error_detected is False
        assert analysis.error_message is None


# ============================================================================
# 2. Network Timeout & Circuit Breaker Stress Tests
# ============================================================================

class TestCircuitBreakerStressAndFastFail:
    """Stress tests circuit breaker tripping, latency constraints (<50ms), and cooldown recovery."""

    def test_freellmapi_429_trips_breaker(self):
        """HTTP 429 response trips circuit breaker and sets failure timestamp."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        assert client._last_freellm_failure == 0.0

        http_err = urllib.error.HTTPError(
            url="http://127.0.0.1:31415/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b'{"error": "rate_limit_exceeded"}')
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            analysis = client.inspect_structured("Query")
            assert client._last_freellm_failure > 0.0
            # Offline heuristic fallback operates safely
            assert isinstance(analysis, VisionAnalysis)

    def test_circuit_breaker_fast_fail_latency_under_50ms(self):
        """
        MANDATORY VERIFICATION: While in cooldown, inspect_structured MUST fail fast
        in strictly under 50ms, never attempting network operations.
        """
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        client._last_freellm_failure = time.time()
        client._last_ollama_failure = time.time()

        with patch("urllib.request.urlopen") as mock_url:
            t0 = time.perf_counter()
            analysis = client.inspect_structured("Inspect active window")
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # Empirical check: must be < 50ms (in practice < 5ms)
            assert elapsed_ms < 50.0, f"Fast-fail took {elapsed_ms:.2f}ms (exceeded 50ms threshold)"
            mock_url.assert_not_called()
            assert isinstance(analysis, VisionAnalysis)

    def test_socket_timeout_trips_breaker(self):
        """Socket timeout trips the circuit breaker."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        with patch("urllib.request.urlopen", side_effect=TimeoutError("Socket timed out after 7.0s")):
            analysis = client.inspect_structured("Check screen")
            assert client._last_freellm_failure > 0.0
            assert isinstance(analysis, VisionAnalysis)

    def test_connection_refused_trips_breaker(self):
        """ConnectionRefusedError trips the circuit breaker."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        url_err = urllib.error.URLError(ConnectionRefusedError("No connection could be made"))
        with patch("urllib.request.urlopen", side_effect=url_err):
            analysis = client.inspect_structured("Check screen")
            assert client._last_freellm_failure > 0.0
            assert isinstance(analysis, VisionAnalysis)

    def test_http_500_server_error_trips_breaker(self):
        """HTTP 500 internal server error trips the circuit breaker."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        http_err = urllib.error.HTTPError(
            url="http://127.0.0.1:31415/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b'{"error": "internal_error"}')
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            client.inspect_structured("Check screen")
            assert client._last_freellm_failure > 0.0

    def test_burst_calls_during_cooldown_execution_speed(self):
        """100 rapid calls during cooldown complete in < 250ms total without hangs."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        client._last_freellm_failure = time.time()
        client._last_ollama_failure = time.time()

        t0 = time.perf_counter()
        for i in range(100):
            res = client.inspect_structured(f"Query {i}")
            assert res is not None
        total_ms = (time.perf_counter() - t0) * 1000.0

        assert total_ms < 250.0, f"100 calls during cooldown took {total_ms:.2f}ms (threshold 250ms)"

    def test_cooldown_expiration_and_recovery(self):
        """After cooldown window elapses, the client attempts network call and recovers on 200 OK."""
        client = MultimodalVisionClient(cooldown_seconds=0.1)  # 100ms cooldown
        client._last_freellm_failure = time.time() - 0.2       # Cooldown already expired

        mock_resp_data = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "extracted_text": "Recovered Successfully",
                        "description": "Live endpoint",
                        "error_detected": False,
                        "error_message": None
                    })
                }
            }]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = mock_resp_data
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_url:
            analysis = client.inspect_structured("Check screen")
            mock_url.assert_called_once()
            assert analysis.extracted_text == "Recovered Successfully"

    def test_ollama_cascade_circuit_breaker(self):
        """When all Ollama cascade models fail, Ollama breaker trips and fast-fails."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)
        # FreeLLM in cooldown
        client._last_freellm_failure = time.time()

        with patch.object(client, "_query_ollama_single", return_value=None):
            analysis = client.inspect_structured("Check screen")
            assert client._last_ollama_failure > 0.0

        # Next call skips Ollama
        with patch.object(client, "_query_ollama_cascade") as mock_cascade:
            analysis2 = client.inspect_structured("Check screen")
            mock_cascade.assert_not_called()


# ============================================================================
# 3. UI Error Text & Verification Edge Cases
# ============================================================================

class TestUIErrorTextEdgeCases:
    """Stress tests subtle error keywords, mixed casing, Hindi error phrases, and UI verification."""

    @pytest.fixture
    def client(self):
        return MultimodalVisionClient()

    @pytest.fixture
    def analyzer(self, client):
        return VisionAnalyzer(vision_client=client)

    @pytest.mark.parametrize("error_text,expected_kw", [
        ("Traceback (most recent call last):\n  File 'a.py', line 1\nZeroDivisionError", "traceback"),
        ("Unhandled Exception in thread 'main'", "exception"),
        ("Fatal: could not read from remote repository", "fatal"),
        ("TASK FAILED with exit code 1", "failed"),
        ("ERROR: File Not Found [Errno 2]", "error"),
        ("सिस्टम त्रुटि: कनेक्शन विफल रहा", "त्रुटि"),
        ("प्रमाणीकरण विफल हो गया", "विफल"),
        ("ERR: memory corruption detected", "err:"),
        ("Application CRASH detected at address 0x0045A", "crash"),
    ])
    def test_subtle_and_multilingual_error_detection(self, client, error_text, expected_kw):
        """Ensures all ERROR_KEYWORDS and Hindi terms are properly caught by lexical scanner."""
        text, has_err, err_msg = client._parse_vision_response(error_text)
        assert has_err is True, f"Failed to detect error in '{error_text}'"
        assert err_msg is not None

    def test_secondary_check_overrides_false_error_detected(self, client):
        """If LLM says error_detected=false but extracted_text contains an error, client corrects it."""
        payload = json.dumps({
            "extracted_text": "Traceback (most recent call last): SystemError",
            "description": "Terminal showing log",
            "error_detected": False,  # Hallucinated false by LLM
            "error_message": None
        })
        analysis = client._parse_json_vision_response(payload)
        assert analysis.error_detected is True
        assert analysis.error_message is not None

    def test_verify_ui_state_active_error_blocks_verification(self, analyzer):
        """Active error dialog strictly blocks UI state verification."""
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="Error: Could not connect to database",
            description="Database dialog",
            error_detected=True,
            error_message="Could not connect to database"
        )
        az = VisionAnalyzer(vision_client=mock_client)
        assert az.verify_ui_state("Database Connection Established") is False

    def test_verify_ui_state_case_insensitivity(self, analyzer):
        """Case insensitivity matching in verify_ui_state."""
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="GOOGLE CHROME - NEW TAB",
            description="Browser window",
            error_detected=False
        )
        az = VisionAnalyzer(vision_client=mock_client)
        assert az.verify_ui_state("google chrome") is True
        assert az.verify_ui_state("Google Chrome") is True
        assert az.verify_ui_state("NEW TAB") is True

    def test_verify_ui_state_empty_description_passes(self, analyzer):
        """Empty expected description always passes."""
        assert analyzer.verify_ui_state("") is True

    def test_verify_ui_state_whitespace_handling(self, analyzer):
        """Leading/trailing whitespace in expected description."""
        mock_client = MagicMock()
        mock_client.inspect_structured.return_value = VisionAnalysis(
            extracted_text="Visual Studio Code",
            description="IDE",
            error_detected=False
        )
        az = VisionAnalyzer(vision_client=mock_client)
        # Even with surrounding whitespace, when no error is present it succeeds
        assert az.verify_ui_state("   Visual Studio Code   ") is True

    def test_benign_words_avoid_false_positive_heuristic(self, client):
        """Ensure normal desktop words don't get falsely categorized as errors."""
        benign_samples = [
            "Desktop workspace with icons",
            "Running Project SAM v1.0",
            "Effortless automation for Windows",
            "Mirror display configuration",
        ]
        for sample in benign_samples:
            text, has_err, err_msg = client._parse_vision_response(sample)
            assert has_err is False, f"False positive error detected in '{sample}'"


# ============================================================================
# 4. Multithreaded Concurrency Stress Tests
# ============================================================================

class TestMultithreadedConcurrencyStress:
    """Stress tests concurrent operations under high thread contention."""

    def test_concurrent_client_inspection_with_simulated_outage(self):
        """30 concurrent threads hitting client while circuit breaker trips."""
        client = MultimodalVisionClient(cooldown_seconds=30.0)

        def worker(thread_id: int):
            # Simulate intermittent network errors
            if thread_id % 3 == 0:
                with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                    url="http://127.0.0.1:31415", code=429, msg="Too Many Requests", hdrs={}, fp=io.BytesIO(b"{}")
                )):
                    return client.inspect_structured(f"Thread {thread_id} prompt")
            else:
                return client.inspect_structured(f"Thread {thread_id} prompt")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(30)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 30
        for r in results:
            assert isinstance(r, VisionAnalysis)

    def test_concurrent_analyzer_verification(self):
        """30 concurrent threads verifying UI states on shared VisionAnalyzer."""
        analyzer = VisionAnalyzer()

        def worker(i: int):
            return analyzer.verify_ui_state(f"Expected State {i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(30)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 30
        assert all(isinstance(r, bool) for r in results)

    def test_concurrent_screen_capture_no_crashes(self):
        """10 concurrent threads capturing screen simultaneously to temporary directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            capture_engine = ScreenCaptureEngine(default_output_dir=tmp_dir)

            def capture_worker(i: int):
                # Unique target per thread to avoid race collision
                target = os.path.join(tmp_dir, f"capture_{i}_{time.time_ns()}.png")
                return capture_engine.capture(output_path=target)

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(capture_worker, i) for i in range(10)]
                paths = [f.result() for f in concurrent.futures.as_completed(futures)]

            assert len(paths) == 10
            for p in paths:
                assert os.path.exists(p)
                assert os.path.getsize(p) > 0


# ============================================================================
# 5. Multilingual Screen Intent Parsing Tests (src/sam/brain/intent.py)
# ============================================================================

class TestScreenIntentParsingAdversarial:
    """Stress tests intent parser screen queries in English and Hinglish."""

    @pytest.fixture
    def parser(self):
        return MultilingualIntentParser()

    @pytest.mark.parametrize("query", [
        "what does this error say",
        "what does error say",
        "what is on the screen",
        "what is on screen",
        "read the screen",
        "read screen",
        "inspect the screen",
        "inspect screen",
        "check the screen",
        "check screen",
        "check my screen",
        "what's the error",
        "what is the error",
        "screen par kya likha hai",
        "error kya hai",
        "error batao",
        "error padho",
        "ye error kya keh raha hai",
    ])
    def test_supported_screen_queries_route_to_inspect_screen(self, parser, query):
        """Verifies all defined English and Hinglish screen queries route to inspect_screen."""
        decision = parser.parse(query)
        assert decision is not None, f"Failed to parse query: '{query}'"
        assert decision.decision_type == "tool_call"
        assert decision.tool_call.tool_name == "inspect_screen"
        assert decision.tool_call.risk_level == RiskLevel.LOW

    @pytest.mark.parametrize("cased_query", [
        "WHAT DOES THIS ERROR SAY",
        "Read Screen!",
        "   CHECK MY SCREEN   ",
        "Screen Par Kya Likha Hai?",
        "ERROR BATAO",
    ])
    def test_case_and_punctuation_insensitivity_screen_queries(self, parser, cased_query):
        """Punctuation and casing variations on screen queries."""
        decision = parser.parse(cased_query)
        assert decision is not None, f"Failed to parse cased query: '{cased_query}'"
        assert decision.tool_call.tool_name == "inspect_screen"

    @pytest.mark.parametrize("dispatch_phrase,expected_handled", [
        ("read screen", True),
        ("screen par kya dikh raha hai", False),  # EMPIRICAL TEST: matches likha, not dikh
        ("is there an error on screen", False),    # EMPIRICAL TEST: not in current regex patterns
    ])
    def test_empirical_dispatch_phrases(self, parser, dispatch_phrase, expected_handled):
        """
        Adversarially tests the exact phrases specified in dispatch instructions:
        - 'read screen' (PASSES)
        - 'screen par kya dikh raha hai' (RETURNS None - UNHANDLED)
        - 'is there an error on screen' (RETURNS None - UNHANDLED)
        """
        decision = parser.parse(dispatch_phrase)
        if expected_handled:
            assert decision is not None
            assert decision.tool_call.tool_name == "inspect_screen"
        else:
            # Empirical verification of the gap
            assert decision is None, (
                f"Expected '{dispatch_phrase}' to return None, but returned: {decision}"
            )

    @pytest.mark.parametrize("non_screen_query", [
        "fix this error in main.py",
        "adjust screen brightness to 50%",
        "open error_log.txt",
        "search for screen recording software",
    ])
    def test_non_screen_queries_do_not_route_to_inspect_screen(self, parser, non_screen_query):
        """Queries containing 'screen' or 'error' but intending other actions must NOT trigger inspect_screen."""
        decision = parser.parse(non_screen_query)
        if decision and decision.tool_call:
            assert decision.tool_call.tool_name != "inspect_screen"
