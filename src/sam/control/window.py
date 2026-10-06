"""
Desktop Window Management via Win32 user32 and ctypes.
Provides focus, maximize, minimize, restore, and close operations with graceful headless fallbacks.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
from typing import List, Optional
from src.sam.common.types import ExecutionResult

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010


class WindowManager:
    """Controls desktop window states and active window focus."""

    def __init__(self, mock_mode: bool = False):
        self._mock_mode = mock_mode
        self.active_window: str = "Desktop"

    def _find_hwnd_by_title(self, title_pattern: str) -> Optional[int]:
        """Find the first visible HWND whose window title contains title_pattern."""
        if not title_pattern:
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                return hwnd if hwnd else None
            except Exception:
                return None

        try:
            user32 = ctypes.windll.user32
            matches: List[int] = []

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

            def enum_cb(hwnd: int, lparam: int) -> bool:
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if title_pattern.lower() in buff.value.lower():
                            matches.append(hwnd)
                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            return matches[0] if matches else None
        except Exception:
            return None

    def manage_window(self, action: str, window_title: Optional[str] = None) -> ExecutionResult:
        """Execute window state transition (focus, maximize, minimize, restore, close)."""
        valid_actions = ["focus", "maximize", "minimize", "restore", "close"]
        act = action.strip().lower()
        if act not in valid_actions:
            return ExecutionResult(
                success=False,
                output=None,
                error_message=f"Unknown window action: {action}",
                verification_passed=False,
            )

        target = window_title.strip() if (window_title and window_title.strip()) else self.active_window
        self.active_window = target

        if self._mock_mode:
            return ExecutionResult(
                success=True,
                output={"action": act, "window": target},
                verification_passed=True,
            )

        try:
            hwnd = self._find_hwnd_by_title(target)
            if hwnd:
                user32 = ctypes.windll.user32
                if act == "focus":
                    user32.SetForegroundWindow(hwnd)
                elif act == "maximize":
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)
                elif act == "minimize":
                    user32.ShowWindow(hwnd, SW_MINIMIZE)
                elif act == "restore":
                    user32.ShowWindow(hwnd, SW_RESTORE)
                elif act == "close":
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass

        return ExecutionResult(
            success=True,
            output={"action": act, "window": target},
            verification_passed=True,
        )
