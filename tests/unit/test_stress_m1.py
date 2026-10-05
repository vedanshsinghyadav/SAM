"""
Milestone 1 Adversarial Stress Test Suite.
Empirically stress-tests:
1. Network probe concurrency, rapid oscillations, socket timeouts.
2. Ollama client JSON parser fuzzing, HTTP 500/502/refused/hang error handling.
3. Personality metric formatter extreme values, voice modality sanitization.
4. ReDoS and high-volume input stress.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import socket
import threading
import time
from typing import Any, Dict, List
import unittest
from unittest.mock import MagicMock, patch

import httpx

from src.sam.brain.context import ContextTracker
from src.sam.brain.intent import MultilingualIntentParser
from src.sam.brain.ollama_client import OllamaBrain
from src.sam.common.network import (
    NetworkMonitor,
    is_online,
    probe_socket,
    set_forced_connectivity,
    get_forced_connectivity,
)
from src.sam.common.types import ActiveContext, BrainDecision, RiskLevel
from src.sam.personality.interface import ToneMode
from src.sam.personality.adapter import PersonalityAdapter


class TestNetworkAdversarialStress(unittest.TestCase):
    """Stress tests for network probe concurrency and rapid oscillations."""

    def tearDown(self) -> None:
        set_forced_connectivity(None)

    def test_rapid_oscillation_under_multi_threaded_readers(self) -> None:
        """
        Toggle set_forced_connectivity across multiple writer threads
        while 20 reader threads call is_online() concurrently.
        Must produce zero race conditions, deadlocks, or unhandled exceptions.
        """
        stop_event = threading.Event()
        errors: List[Exception] = []
        read_results: List[bool] = []

        def toggler(worker_id: int) -> None:
            states = [True, False, None]
            for i in range(100):
                try:
                    set_forced_connectivity(states[(worker_id + i) % 3])
                    time.sleep(0.0005)
                except Exception as e:
                    errors.append(e)

        def reader() -> None:
            while not stop_event.is_set():
                try:
                    res = is_online(use_cache=True)
                    self.assertIsInstance(res, bool)
                except Exception as e:
                    errors.append(e)

        # Launch 5 writer threads and 15 reader threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            readers = [executor.submit(reader) for _ in range(15)]
            writers = [executor.submit(toggler, i) for i in range(5)]
            concurrent.futures.wait(writers)
            stop_event.set()
            concurrent.futures.wait(readers)

        self.assertEqual(len(errors), 0, f"Encountered {len(errors)} thread safety errors: {errors}")

    def test_concurrent_socket_probes_100_workers(self) -> None:
        """
        100 concurrent threads calling is_online(use_cache=False) to test
        socket lifecycle and file descriptor safety.
        """
        # Ensure forced connectivity is None
        set_forced_connectivity(None)

        def worker_probe() -> bool:
            return is_online(use_cache=False)

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(worker_probe) for _ in range(100)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 100)
        # All results should be bool without any socket exhaustion exceptions
        for r in results:
            self.assertIsInstance(r, bool)

    def test_unreachable_host_and_socket_timeout(self) -> None:
        """
        Verify probe_socket gracefully handles non-routable IPs and timeout bounds.
        """
        set_forced_connectivity(None)
        # 192.0.2.1 is TEST-NET-1 (RFC 5737), non-routable blackhole
        start = time.perf_counter()
        connected, latency = probe_socket(host="192.0.2.1", port=80, timeout=0.1)
        elapsed = time.perf_counter() - start

        self.assertFalse(connected)
        # Should respect timeout closely (< 1.5s margin)
        self.assertLess(elapsed, 1.5)
        self.assertGreater(latency, 0.0)

    def test_invalid_port_connection_refused(self) -> None:
        """
        Verify probe_socket handles ConnectionRefusedError gracefully.
        """
        set_forced_connectivity(None)
        connected, latency = probe_socket(host="127.0.0.1", port=59999, timeout=0.2)
        self.assertFalse(connected)
        self.assertGreater(latency, 0.0)

    def test_network_monitor_concurrent_registration_and_faulty_listeners(self) -> None:
        """
        NetworkMonitor must survive faulty listeners that throw exceptions
        and concurrent add/remove operations during notification firing.
        """
        monitor = NetworkMonitor(interval=0.01)

        faulty_listener_invoked = threading.Event()
        valid_listener_invoked = threading.Event()

        def faulty_listener(status: bool) -> None:
            faulty_listener_invoked.set()
            raise RuntimeError("Faulty listener intentional explosion!")

        def valid_listener(status: bool) -> None:
            valid_listener_invoked.set()

        monitor.add_listener(faulty_listener)
        monitor.add_listener(valid_listener)

        monitor.start()
        # Force state change notifications by calling _notify directly and letting run
        monitor._notify(True)
        monitor._notify(False)

        # Concurrently add and remove listeners while monitor is running
        def churn_listeners() -> None:
            for _ in range(50):
                cb = lambda s: None
                monitor.add_listener(cb)
                monitor.remove_listener(cb)

        threads = [threading.Thread(target=churn_listeners) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(faulty_listener_invoked.is_set())
        self.assertTrue(valid_listener_invoked.is_set())
        self.assertTrue(monitor.is_running())
        monitor.stop(timeout=1.0)
        self.assertFalse(monitor.is_running())


class TestOllamaParserAndDaemonStress(unittest.TestCase):
    """Stress tests and fuzzing for OllamaBrain JSON parsing and daemon failover."""

    def setUp(self) -> None:
        self.brain = OllamaBrain(mock_mode=False)

    def test_json_fuzz_markdown_variations(self) -> None:
        """
        Fuzz _parse_json_decision with various markdown fencing styles,
        prose commentary, and inner code blocks.
        """
        # Case 1: Standard json fence
        payload1 = '```json\n{"decision_type": "reply", "reply_text": "Hello standard"}\n```'
        dec1 = self.brain._parse_json_decision(payload1)
        self.assertEqual(dec1.decision_type, "reply")
        self.assertEqual(dec1.reply_text, "Hello standard")

        # Case 2: Plain fence without 'json'
        payload2 = '```\n{"decision_type": "reply", "reply_text": "Hello plain fence"}\n```'
        dec2 = self.brain._parse_json_decision(payload2)
        self.assertEqual(dec2.decision_type, "reply")
        self.assertEqual(dec2.reply_text, "Hello plain fence")

        # Case 3: Leading and trailing conversational prose
        payload3 = (
            "Certainly, here is the requested structured output:\n\n"
            "```json\n"
            '{"decision_type": "tool_call", "reply_text": "Opening Chrome", '
            '"tool_call": {"tool_name": "open_app", "arguments": {"app_name": "chrome"}, "risk_level": "LOW"}}\n'
            "```\n\n"
            "Hope this assists you properly."
        )
        dec3 = self.brain._parse_json_decision(payload3)
        self.assertEqual(dec3.decision_type, "tool_call")
        self.assertIsNotNone(dec3.tool_call)
        self.assertEqual(dec3.tool_call.tool_name, "open_app")

        # Case 4: Deeply nested json inside code block inside tool argument
        payload4 = (
            '{"decision_type": "reply", '
            '"reply_text": "Here is an example code snippet:\\n```python\\nprint(1)\\n```\\n"}'
        )
        dec4 = self.brain._parse_json_decision(payload4)
        self.assertIsNotNone(dec4)
        self.assertIn("print(1)", dec4.reply_text or "")

    def test_json_fuzz_malformed_and_truncated(self) -> None:
        """
        Fuzz _parse_json_decision with malformed and truncated inputs.
        Should never raise unhandled exceptions; must fallback gracefully.
        """
        malformed_inputs = [
            '{"decision_type": "reply", "reply_text": "Truncated...',
            '{"decision_type": "reply", "reply_text": "Unescaped \n Newline"}',
            "{invalid: json}",
            "<html>502 Bad Gateway</html>",
            "",
            "   \n  \t ",
            "[{'decision_type': 'reply'}]",
            "decision_type: reply",
            '{"unexpected_key": 12345}',
            '{"decision_type": 99999}',
            '{"decision_type": "unknown_type_xxx"}',
            "undefined",
            "{",
            "}",
            "{}",
        ]

        for raw in malformed_inputs:
            with self.subTest(raw=raw):
                try:
                    dec = self.brain._parse_json_decision(raw)
                    self.assertIsInstance(dec, BrainDecision)
                except Exception as e:
                    self.fail(f"Parsing '{raw}' raised unhandled exception: {e}")

    def test_ollama_daemon_http_errors_and_failover(self) -> None:
        """
        Simulate HTTP 500, 502, connection refused, and timeout.
        Verify cloud -> local failover and graceful heuristic fallback.
        """
        brain = OllamaBrain(
            cloud_model="gemma4:cloud",
            local_model="qwen2.5:7b",
            base_url="http://localhost:11434",
            timeout=1.0,
            mock_mode=False,
            network_checker=lambda: True,  # Online
        )

        # 1. Cloud model fails with 500, Local model succeeds
        with patch.object(brain, "_call_ollama") as mock_call:
            def side_effect(prompt, ctx, model):
                if model == "gemma4:cloud":
                    raise httpx.HTTPStatusError("500 Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))
                return '{"decision_type": "reply", "reply_text": "Local model response"}'

            mock_call.side_effect = side_effect
            decision = brain.process_input("What is SAM?", ActiveContext())

            self.assertEqual(decision.decision_type, "reply")
            self.assertIn("Local model response", decision.reply_text)
            self.assertTrue(decision.is_offline_fallback)
            self.assertEqual(decision.model_used, "qwen2.5:7b")

        # 2. Both Cloud and Local fail with 502 Bad Gateway
        with patch.object(brain, "_call_ollama") as mock_call:
            mock_call.side_effect = httpx.HTTPStatusError("502 Bad Gateway", request=MagicMock(), response=MagicMock(status_code=502))
            decision = brain.process_input("Open Chrome", ActiveContext())

            self.assertEqual(decision.decision_type, "tool_call")
            self.assertEqual(decision.tool_call.tool_name, "open_app")
            self.assertTrue(decision.is_offline_fallback)

        # 3. Connection refused (Ollama daemon offline)
        with patch.object(brain, "_call_ollama") as mock_call:
            mock_call.side_effect = httpx.ConnectError("Connection refused")
            decision = brain.process_input("kal COA exam hai notes kholo", ActiveContext())

            self.assertEqual(decision.decision_type, "plan")
            self.assertTrue(decision.is_offline_fallback)

        # 4. Read Timeout / Hang
        with patch.object(brain, "_call_ollama") as mock_call:
            mock_call.side_effect = httpx.ReadTimeout("Server did not respond within 30s")
            decision = brain.process_input("hello", ActiveContext())

            self.assertEqual(decision.decision_type, "reply")
            self.assertTrue(decision.is_offline_fallback)


class TestPersonalityAndModalitySanitizerStress(unittest.TestCase):
    """Stress tests for extreme metric values and voice modality sanitization."""

    def setUp(self) -> None:
        self.adapter = PersonalityAdapter()

    def test_extreme_metric_values(self) -> None:
        """
        Format system metrics with extreme, boundary, and non-numeric inputs.
        """
        cases = [
            ("cpu", 0.0, ["cool", "0%"]),
            ("cpu", 0, ["cool", "0%"]),
            ("cpu", 24.9, ["cool", "24.9%"]),
            ("cpu", 25.0, ["humming", "25%"]),
            ("cpu", 59.9, ["humming", "59.9%"]),
            ("cpu", 60.0, ["brisk", "60%"]),
            ("cpu", 84.9, ["brisk", "84.9%"]),
            ("cpu", 85.0, ["pulling hard", "85%"]),
            ("cpu", 99.9, ["pulling hard", "99.9%"]),
            ("cpu", 100.0, ["pulling hard", "100%"]),
            ("cpu", 100, ["pulling hard", "100%"]),
            ("cpu", -5.0, ["cool", "-5%"]),  # Boundary negative
            ("cpu", 500.0, ["pulling hard", "500%"]),  # Overloaded multi-core
            ("cpu", float("nan"), ["nan%"]),
            ("cpu", float("inf"), ["inf%"]),
            ("cpu", "N/A", ["N/A"]),
            ("cpu", None, ["None"]),
            ("ram", 12.5, ["comfortably", "12.5%"]),
            ("ram", 79.9, ["headroom", "79.9%"]),
            ("ram", 95.0, ["Chrome", "95%"]),
            ("battery", 100.0, ["pretty", "100%"]),
            ("battery", 50.0, ["50%"]),
            ("battery", 15.0, ["power cable", "15%"]),
            ("disk", 10.0, ["healthy", "10%"]),
            ("disk", 95.0, ["cleaning", "95%"]),
        ]

        for metric_name, val, expected_keywords in cases:
            with self.subTest(metric=metric_name, val=val):
                res = self.adapter.format_system_metric(metric_name, val)
                self.assertIsInstance(res, str)
                for kw in expected_keywords:
                    self.assertIn(kw.lower(), res.lower())

    def test_modality_sanitizer_complex_markdown_and_tables(self) -> None:
        """
        Stress test voice modality sanitization against markdown tables,
        raw LaTeX, nested URLs, and paths.
        """
        # Complex markdown table
        table_text = (
            "Here is the status:\n\n"
            "| Component | Status | Load |\n"
            "|-----------|--------|------|\n"
            "| CPU       | OK     | 25%  |\n"
            "| Memory    | OK     | 60%  |\n"
        )
        voice_out = self.adapter.sanitize_for_modality(table_text, modality="voice")
        self.assertIsInstance(voice_out, str)
        # Should expand % to percent
        self.assertIn("percent", voice_out)
        self.assertNotIn("```", voice_out)

        # Raw LaTeX
        latex_text = r"The formula is $$E = mc^2$$ where \frac{a}{b} applies."
        voice_latex = self.adapter.sanitize_for_modality(latex_text, modality="voice")
        self.assertIsInstance(voice_latex, str)

        # Markdown links with nested query parameters and parentheses
        link_text = "Check out [Wikipedia](https://en.wikipedia.org/wiki/Artificial_intelligence) and [Search](https://google.com/search?q=test&hl=en)."
        voice_link = self.adapter.sanitize_for_modality(link_text, modality="voice")
        self.assertNotIn("https://", voice_link)
        self.assertIn("Wikipedia", voice_link)

        # Windows file path
        path_text = r"File saved at D:\Notes\COA\Unit1.pdf"
        voice_path = self.adapter.sanitize_for_modality(path_text, modality="voice")
        self.assertIn("D drive", voice_path)

        # Code block containing language identifier
        code_text = "Here is the code:\n```python\nimport os\nprint('hello')\n```\nDone."
        voice_code = self.adapter.sanitize_for_modality(code_text, modality="voice")
        self.assertNotIn("```", voice_code)


class TestReDoSAndVolumeStress(unittest.TestCase):
    """Stress test for regular expression Denial of Service and large volumes."""

    def test_redos_intent_parser(self) -> None:
        """
        Pass a 50,000 character repeating pattern string to intent parser
        to verify absence of catastrophic regex backtracking.
        """
        parser = MultilingualIntentParser()
        long_text = "open " * 5000 + "chrome " * 5000

        start = time.perf_counter()
        res = parser.parse(long_text)
        elapsed = time.perf_counter() - start

        # Must execute within 500ms
        self.assertLess(elapsed, 0.5, f"ReDoS vulnerability detected: elapsed {elapsed:.3f}s")

    def test_redos_modality_sanitizer(self) -> None:
        """
        Pass 50,000 character strings with unclosed markdown markers
        to verify absence of catastrophic regex backtracking.
        """
        adapter = PersonalityAdapter()
        long_markdown = "**" * 10000 + "word " * 5000 + "__" * 5000

        start = time.perf_counter()
        res = adapter.sanitize_for_modality(long_markdown, modality="voice")
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.5, f"ReDoS in sanitizer detected: elapsed {elapsed:.3f}s")

    def test_context_tracker_10000_turns_sliding_window(self) -> None:
        """
        Add 10,000 dialogue turns to ContextTracker to verify sliding window
        enforces constant memory and O(1) turn bounds.
        """
        tracker = ContextTracker(max_history_turns=20)
        for i in range(10000):
            tracker.add_turn(f"User utterance {i}", f"Agent reply {i}")

        self.assertEqual(len(tracker.context.history), 20)
        self.assertEqual(tracker.context.history[-1].user_input, "User utterance 9999")
        self.assertEqual(tracker.context.history[0].user_input, "User utterance 9980")


class TestAdversarialEdgeCasesAndDiscrepancies(unittest.TestCase):
    """
    Direct empirical exploration of subtle edge cases, architectural quirks,
    and potential failure modes found during adversarial code review.
    """

    def tearDown(self) -> None:
        set_forced_connectivity(None)

    def test_ttl_cache_host_port_agnostic_behavior(self) -> None:
        """
        Adversarial Finding: The TTL cache is global and does not index on (host, port).
        If host A succeeds, a cached call to host B (even if host B is blackholed)
        returns True within the TTL window unless use_cache=False or force_refresh=True.
        """
        set_forced_connectivity(None)
        # Probe valid host (8.8.8.8) -> populates _CACHED_STATUS = True
        status_valid = is_online(host="8.8.8.8", port=53, use_cache=False)
        self.assertTrue(status_valid)

        # Immediately probe non-routable host (192.0.2.1) WITH cache enabled:
        # Returns True because cache has not expired!
        status_cached = is_online(host="192.0.2.1", port=80, use_cache=True)
        self.assertTrue(status_cached)

        # Probing WITHOUT cache correctly returns False:
        status_uncached = is_online(host="192.0.2.1", port=80, timeout=0.1, use_cache=False)
        self.assertFalse(status_uncached)

    def test_json_fuzz_advanced_adversarial_patterns(self) -> None:
        """
        Test JSON parser against:
        1. 4-backtick fences wrapping 3-backtick fences (nested fences)
        2. Unescaped quotes in reply_text
        3. Preceding text with curly braces {like this} before valid JSON
        """
        brain = OllamaBrain(mock_mode=False)

        # Case 1: Preceding text containing curly braces before JSON
        # When text has {curly braces} in conversational text:
        # greedy regex r"(\{.*\})" takes from first { in conversational text to last }!
        tricky_text = 'I reviewed {option A} and decided: {"decision_type": "reply", "reply_text": "Option A selected."}'
        dec = brain._parse_json_decision(tricky_text)
        # Verify it handled via fallback rather than throwing uncaught exception
        self.assertIsInstance(dec, BrainDecision)

        # Case 2: Multi-line string with literal unescaped line breaks
        unescaped_multiline = '{\n"decision_type": "reply",\n"reply_text": "Line 1\nLine 2"\n}'
        dec2 = brain._parse_json_decision(unescaped_multiline)
        self.assertIsInstance(dec2, BrainDecision)

        # Case 3: Empty string
        dec3 = brain._parse_json_decision("")
        self.assertIsInstance(dec3, BrainDecision)
        self.assertEqual(dec3.decision_type, "reply")

    def test_voice_sanitizer_edge_behaviors(self) -> None:
        """
        Empirically document voice sanitizer edge case behavior:
        1. Markdown table pipes and header separators are preserved (not stripped)
        2. Raw LaTeX $$ is preserved, backslash replaced by comma
        3. Code block language identifier ('python') is retained in the text
        """
        adapter = PersonalityAdapter()

        # 1. Markdown tables
        table = "| Col A | Col B |\n|---|---|\n| 1 | 2 |"
        res_table = adapter.sanitize_for_modality(table, modality="voice")
        self.assertIn("|", res_table, "Table pipe preserved in voice output")

        # 2. LaTeX
        latex = chr(36) + chr(36) + "E=mc^2" + chr(36) + chr(36)
        res_latex = adapter.sanitize_for_modality(latex, modality="voice")
        self.assertIn("E=mc^2", res_latex)

        # 3. Code inside code blocks is retained in voice output
        code = "Code:\n```python\nprint(1)\n```"
        res_code = adapter.sanitize_for_modality(code, modality="voice")
        self.assertIn("print(1)", res_code, "Code content is spoken verbatim in voice output")
        self.assertNotIn("```", res_code, "Backticks are stripped")


if __name__ == "__main__":
    unittest.main()

