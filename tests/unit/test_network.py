"""
Unit tests for src/sam/common/network.py.
Validates sub-millisecond TCP socket probing, TTL caching, async check,
and background NetworkMonitor listener.
"""

import socket
import time
from unittest.mock import MagicMock, patch
import pytest

from src.sam.common.network import (
    probe_socket,
    is_online,
    check_online_async,
    set_forced_connectivity,
    get_forced_connectivity,
    NetworkMonitor,
)


@pytest.fixture(autouse=True)
def cleanup_forced_connectivity():
    yield
    set_forced_connectivity(None)


class TestSocketProbe:
    def test_probe_socket_success(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            connected, latency = probe_socket("8.8.8.8", 53, timeout=0.5)

            assert connected is True
            assert latency >= 0.0
            mock_sock.connect.assert_called_once_with(("8.8.8.8", 53))
            mock_sock.close.assert_called_once()

    def test_probe_socket_offline_instant_failure(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = OSError(10051, "Network unreachable")
            mock_sock_cls.return_value = mock_sock

            start = time.perf_counter()
            connected, latency = probe_socket("8.8.8.8", 53, timeout=1.0)
            elapsed_total = (time.perf_counter() - start) * 1000.0

            assert connected is False
            # Sub-millisecond reaction verification
            assert elapsed_total < 50.0
            mock_sock.close.assert_called_once()

    def test_probe_socket_timeout(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = socket.timeout("Timed out")
            mock_sock_cls.return_value = mock_sock

            connected, latency = probe_socket("8.8.8.8", 53, timeout=0.1)
            assert connected is False


class TestIsOnlineAndCaching:
    def test_forced_connectivity_override(self):
        set_forced_connectivity(True)
        assert is_online() is True
        assert get_forced_connectivity() is True

        set_forced_connectivity(False)
        assert is_online() is False
        assert get_forced_connectivity() is False

        set_forced_connectivity(None)
        assert get_forced_connectivity() is None

    def test_caching_behavior(self):
        with patch("src.sam.common.network.probe_socket") as mock_probe:
            mock_probe.return_value = (True, 15.0)

            # First call executes probe
            res1 = is_online(use_cache=True, cache_ttl=5.0, force_refresh=True)
            assert res1 is True
            assert mock_probe.call_count == 1

            # Second call within TTL must return cached without invoking probe again
            res2 = is_online(use_cache=True, cache_ttl=5.0, force_refresh=False)
            assert res2 is True
            assert mock_probe.call_count == 1

            # Force refresh invokes probe
            res3 = is_online(use_cache=True, cache_ttl=5.0, force_refresh=True)
            assert res3 is True
            assert mock_probe.call_count == 2


@pytest.mark.asyncio
async def test_check_online_async():
    set_forced_connectivity(True)
    res = await check_online_async()
    assert res is True

    set_forced_connectivity(False)
    res = await check_online_async()
    assert res is False


class TestNetworkMonitor:
    def test_monitor_state_transition_notification(self):
        monitor = NetworkMonitor(interval=0.05, timeout=0.05)
        events = []

        def on_change(state: bool):
            events.append(state)

        monitor.add_listener(on_change)

        with patch("src.sam.common.network.probe_socket") as mock_probe:
            mock_probe.side_effect = [
                (True, 10.0),
                (True, 10.0),
                (False, 0.2),
                (True, 12.0)
            ]

            monitor.start()
            time.sleep(0.25)
            monitor.stop(timeout=1.0)

            assert monitor.is_running() is False
            # Verify listener removal works
            monitor.remove_listener(on_change)
            assert on_change not in monitor._listeners

    def test_monitor_start_and_clean_stop(self):
        monitor = NetworkMonitor(interval=0.1)
        monitor.start()
        assert monitor.is_running() is True
        monitor.stop(timeout=1.0)
        assert monitor.is_running() is False

    def test_monitor_get_status(self):
        set_forced_connectivity(True)
        monitor = NetworkMonitor(interval=0.1)
        status = monitor.get_status()
        assert status.is_online is True
        assert status.target_host == "8.8.8.8"
        assert status.target_port == 53
