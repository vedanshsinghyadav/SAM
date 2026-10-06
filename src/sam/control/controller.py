"""
Unified ComputerController Facade.
Aggregates AppManager, WindowManager, FileController, SystemController, and TerminalRunner.
Conforms to IComputerController protocol.
"""

from __future__ import annotations
import os
import tempfile
from typing import Any, Dict, List, Optional
from src.sam.common.types import ExecutionResult
from src.sam.control.interface import IComputerController
from src.sam.control.app import AppManager
from src.sam.control.window import WindowManager
from src.sam.control.file import FileController
from src.sam.control.system import SystemController
from src.sam.control.terminal import TerminalRunner


class ComputerController(IComputerController):
    """Unified master controller coordinating all Windows OS sub-controllers."""

    def __init__(self, workspace_root: Optional[str] = None, mock_mode: bool = False):
        self.workspace_root: str = os.path.abspath(workspace_root or tempfile.gettempdir())
        self.mock_mode: bool = mock_mode
        self.app_manager = AppManager(mock_mode=mock_mode)
        self.window_manager = WindowManager(mock_mode=mock_mode)
        self.file_controller = FileController(workspace_root=self.workspace_root)
        self.system_controller = SystemController(mock_mode=mock_mode)
        self.terminal_runner = TerminalRunner(mock_mode=mock_mode)

    @property
    def running_apps(self) -> Dict[str, int]:
        return self.app_manager.running_apps

    @running_apps.setter
    def running_apps(self, val: Dict[str, int]) -> None:
        self.app_manager.running_apps = val

    @property
    def active_window(self) -> str:
        return self.window_manager.active_window

    @active_window.setter
    def active_window(self, val: str) -> None:
        self.window_manager.active_window = val

    @property
    def current_volume(self) -> int:
        return self.system_controller.current_volume

    @current_volume.setter
    def current_volume(self, val: int) -> None:
        self.system_controller.current_volume = val

    @property
    def current_brightness(self) -> int:
        return self.system_controller.current_brightness

    @current_brightness.setter
    def current_brightness(self, val: int) -> None:
        self.system_controller.current_brightness = val

    @property
    def media_state(self) -> str:
        return self.system_controller.media_state

    @media_state.setter
    def media_state(self, val: str) -> None:
        self.system_controller.media_state = val

    @property
    def notifications(self) -> List[Dict[str, Any]]:
        return self.system_controller.notifications

    @notifications.setter
    def notifications(self, val: List[Dict[str, Any]]) -> None:
        self.system_controller.notifications = val

    def open_app(self, app_name: str) -> ExecutionResult:
        res = self.app_manager.open_app(app_name)
        if res.success:
            self.window_manager.active_window = f"{app_name} - Main Window"
        return res

    def close_app(self, process_or_name: str) -> ExecutionResult:
        return self.app_manager.close_app(process_or_name)

    def manage_window(self, action: str, window_title: Optional[str] = None) -> ExecutionResult:
        return self.window_manager.manage_window(action, window_title)

    def file_action(self, action: str, **kwargs) -> ExecutionResult:
        return self.file_controller.file_action(action, **kwargs)

    def control_volume(self, level: Optional[int] = None, delta: Optional[int] = None) -> ExecutionResult:
        return self.system_controller.control_volume(level=level, delta=delta)

    def control_brightness(self, level: Optional[int] = None) -> ExecutionResult:
        return self.system_controller.control_brightness(level=level)

    def control_media(self, command: str) -> ExecutionResult:
        return self.system_controller.control_media(command)

    def run_terminal(self, command: str, shell: str = "powershell", timeout: int = 30) -> ExecutionResult:
        return self.terminal_runner.run_terminal(command, shell=shell, timeout=timeout)

    def get_system_stats(self) -> Dict[str, Any]:
        stats = self.system_controller.get_system_stats()
        stats["running_apps"] = len(self.app_manager.running_apps)
        return stats

    def read_notifications(self) -> List[Dict[str, Any]]:
        return self.system_controller.read_notifications()
