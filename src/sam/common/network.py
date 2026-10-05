"""
SAM Ultra-Fast Offline Network Probe & Monitoring Engine.
Provides sub-millisecond TCP socket probing to 8.8.8.8:53, TTL caching, async check,
and background event listener for automatic cloud-to-local failover.
"""

from __future__ import annotations
import asyncio
import socket
import threading
import time
from typing import Callable, List, Optional, Tuple

from src.sam.common.types import NetworkStatus


# Defaults
DEFAULT_PROBE_HOST = "8.8.8.8"
DEFAULT_PROBE_PORT = 53
DEFAULT_PROBE_TIMEOUT = 1.0  # seconds
DEFAULT_CACHE_TTL = 3.0      # seconds
DEFAULT_MONITOR_INTERVAL = 5.0  # seconds

# Global Test Hook / Forced State
_FORCED_CONNECTIVITY: Optional[bool] = None
_CACHE_LOCK = threading.Lock()
_CACHED_STATUS: Optional[bool] = None
_CACHED_TIME: float = 0.0
_CACHED_LATENCY: Optional[float] = None


def set_forced_connectivity(status: Optional[bool]) -> None:
    """
    Force connectivity state for deterministic unit testing.
    Set to True to simulate online, False to simulate offline, None to restore real probes.
    """
    global _FORCED_CONNECTIVITY, _CACHED_STATUS, _CACHED_TIME, _CACHED_LATENCY
    with _CACHE_LOCK:
        _FORCED_CONNECTIVITY = status
        _CACHED_STATUS = None
        _CACHED_TIME = 0.0
        _CACHED_LATENCY = None


def get_forced_connectivity() -> Optional[bool]:
    """Retrieve current forced connectivity state, or None if real probing is active."""
    return _FORCED_CONNECTIVITY


def probe_socket(
    host: str = DEFAULT_PROBE_HOST,
    port: int = DEFAULT_PROBE_PORT,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
) -> Tuple[bool, float]:
    """
    Execute raw TCP socket connection probe to target IP and port.
    Returns (is_connected: bool, elapsed_ms: float).
    Sub-millisecond on Windows when offline due to immediate kernel route rejection.
    """
    if _FORCED_CONNECTIVITY is not None:
        return (_FORCED_CONNECTIVITY, 0.1)

    start = time.perf_counter()
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return True, elapsed_ms
    except (socket.timeout, OSError, ConnectionRefusedError):
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return False, elapsed_ms
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def is_online(
    host: str = DEFAULT_PROBE_HOST,
    port: int = DEFAULT_PROBE_PORT,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    use_cache: bool = True,
    cache_ttl: float = DEFAULT_CACHE_TTL,
    force_refresh: bool = False,
) -> bool:
    """
    Check if internet connectivity is active.
    Utilizes TTL caching to avoid socket churn during tight execution loops.
    """
    global _CACHED_STATUS, _CACHED_TIME, _CACHED_LATENCY

    if _FORCED_CONNECTIVITY is not None:
        return _FORCED_CONNECTIVITY

    now = time.monotonic()
    if use_cache and not force_refresh:
        with _CACHE_LOCK:
            if _CACHED_STATUS is not None and (now - _CACHED_TIME) < cache_ttl:
                return _CACHED_STATUS

    status, latency = probe_socket(host=host, port=port, timeout=timeout)

    with _CACHE_LOCK:
        _CACHED_STATUS = status
        _CACHED_TIME = now
        _CACHED_LATENCY = latency

    return status


async def check_online_async(
    host: str = DEFAULT_PROBE_HOST,
    port: int = DEFAULT_PROBE_PORT,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
) -> bool:
    """Asynchronous wrapper that runs the socket probe in a thread pool executor."""
    if _FORCED_CONNECTIVITY is not None:
        return _FORCED_CONNECTIVITY
    return await asyncio.to_thread(is_online, host, port, timeout, False, 0.0, True)


class NetworkMonitor:
    """
    Background network monitor thread that regularly probes connectivity
    and notifies registered callbacks upon state transitions (ONLINE <-> OFFLINE).
    """

    def __init__(
        self,
        interval: float = DEFAULT_MONITOR_INTERVAL,
        host: str = DEFAULT_PROBE_HOST,
        port: int = DEFAULT_PROBE_PORT,
        timeout: float = DEFAULT_PROBE_TIMEOUT,
    ) -> None:
        self.interval = interval
        self.host = host
        self.port = port
        self.timeout = timeout
        self._listeners: List[Callable[[bool], None]] = []
        self._listeners_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._current_state: Optional[bool] = None
        self._last_latency: Optional[float] = None
        self._last_checked: float = 0.0

    def add_listener(self, callback: Callable[[bool], None]) -> None:
        """Register a callback receiving (is_online: bool) on state change."""
        with self._listeners_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[bool], None]) -> None:
        """Unregister a listener callback."""
        with self._listeners_lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify(self, new_state: bool) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(new_state)
            except Exception:
                pass  # Do not let listener errors crash monitor

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                online, latency = probe_socket(self.host, self.port, self.timeout)
            except (StopIteration, Exception):
                break
            self._last_latency = latency
            self._last_checked = time.time()

            if self._current_state is None or self._current_state != online:
                old_state = self._current_state
                self._current_state = online
                if old_state is not None:
                    self._notify(online)

            self._stop_event.wait(self.interval)

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="SAM-NetworkMonitor", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal background thread to stop and wait for completion."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    def is_running(self) -> bool:
        """Check if background monitor thread is currently active."""
        return self._thread is not None and self._thread.is_alive()

    def get_status(self) -> NetworkStatus:
        """Return the latest NetworkStatus snapshot."""
        current = (
            self._current_state
            if self._current_state is not None
            else is_online(self.host, self.port, self.timeout)
        )
        return NetworkStatus(
            is_online=current,
            latency_ms=self._last_latency,
            checked_at=self._last_checked or time.time(),
            target_host=self.host,
            target_port=self.port,
        )
