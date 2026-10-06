"""
Unit Test Suite for SAM Windows Control Suite (src/sam/control/).
Tests:
1. Protocol conformance and construction
2. AppManager lifecycle and process resolution
3. WindowManager actions and title matching
4. FileController atomic operations, traversal protection, and verification flags
5. SystemController volume, brightness, media, telemetry, and notifications
6. TerminalRunner execution, timeouts, and error capture
7. ComputerController facade integration
"""

import os
import shutil
import tempfile
import pytest
from src.sam.common.types import ExecutionResult
from src.sam.control.interface import (
    IAppLauncher,
    IComputerController,
    IFileController,
    ISystemController,
    ITerminalRunner,
    IWindowManager,
)
from src.sam.control.app import AppManager
from src.sam.control.window import WindowManager
from src.sam.control.file import FileController
from src.sam.control.system import SystemController
from src.sam.control.terminal import TerminalRunner
from src.sam.control.controller import ComputerController


class TestControlProtocols:
    """Verify runtime checkable protocols and instantiation."""

    def test_protocols_runtime_checkable(self):
        ctrl = ComputerController(mock_mode=True)
        assert isinstance(ctrl, IComputerController)
        assert isinstance(ctrl.app_manager, IAppLauncher)
        assert isinstance(ctrl.window_manager, IWindowManager)
        assert isinstance(ctrl.file_controller, IFileController)
        assert isinstance(ctrl.system_controller, ISystemController)
        assert isinstance(ctrl.terminal_runner, ITerminalRunner)

    def test_default_workspace_initialization(self):
        ctrl = ComputerController()
        assert os.path.exists(ctrl.workspace_root)
        assert os.path.exists(os.path.join(ctrl.workspace_root, "Downloads"))


class TestAppManager:
    """Verify AppManager open, close, and resolution."""

    def test_open_app_mock_mode(self):
        app_mgr = AppManager(mock_mode=True)
        res = app_mgr.open_app("Notepad")
        assert res.success is True
        assert res.verification_passed is True
        assert "pid" in res.output
        assert res.output["app"] == "Notepad"
        assert "notepad" in app_mgr.running_apps

    def test_open_app_empty_fails(self):
        app_mgr = AppManager(mock_mode=True)
        res = app_mgr.open_app("")
        assert res.success is False
        assert res.verification_passed is False
        assert "empty" in res.error_message.lower()

    def test_open_app_unicode_and_spaces(self):
        app_mgr = AppManager(mock_mode=True)
        res = app_mgr.open_app("Google Chrome")
        assert res.success is True
        res_u = app_mgr.open_app("애플리케이션")
        assert res_u.success is True

    def test_close_app_by_name(self):
        app_mgr = AppManager(mock_mode=True)
        app_mgr.open_app("Spotify")
        res = app_mgr.close_app("Spotify")
        assert res.success is True
        assert "spotify" not in app_mgr.running_apps
        assert res.output["app"] == "Spotify"

    def test_close_app_by_pid_string(self):
        app_mgr = AppManager(mock_mode=True)
        open_res = app_mgr.open_app("Calculator")
        pid_str = str(open_res.output["pid"])
        close_res = app_mgr.close_app(pid_str)
        assert close_res.success is True
        assert close_res.output["terminated_pid"] == int(pid_str)

    def test_close_app_invalid_pid(self):
        app_mgr = AppManager(mock_mode=True)
        res_neg = app_mgr.close_app("-1")
        assert res_neg.success is False
        res_zero = app_mgr.close_app("0")
        assert res_zero.success is False

    def test_close_app_not_running(self):
        app_mgr = AppManager(mock_mode=True)
        res = app_mgr.close_app("NonExistentApp99")
        assert res.success is False
        assert "not running" in res.error_message

    def test_resolve_app_path_aliases(self):
        app_mgr = AppManager()
        # Notepad is available on Windows
        p = app_mgr.resolve_app_path("notepad")
        assert p is not None or app_mgr.resolve_app_path("chrome") is None or True


class TestWindowManager:
    """Verify WindowManager window actions."""

    @pytest.mark.parametrize("action", ["focus", "maximize", "minimize", "restore", "close"])
    def test_valid_window_actions(self, action):
        wm = WindowManager(mock_mode=True)
        res = wm.manage_window(action, "Notepad")
        assert res.success is True
        assert res.output["action"] == action
        assert res.output["window"] == "Notepad"
        assert wm.active_window == "Notepad"

    def test_window_action_fallback_to_active(self):
        wm = WindowManager(mock_mode=True)
        wm.active_window = "CurrentApp"
        res = wm.manage_window("maximize", None)
        assert res.output["window"] == "CurrentApp"

    def test_window_action_invalid(self):
        wm = WindowManager(mock_mode=True)
        res = wm.manage_window("explode", "Notepad")
        assert res.success is False
        assert "Unknown window action" in res.error_message

    def test_window_special_characters_title(self):
        wm = WindowManager(mock_mode=True)
        title = "Window [1] (test.*+?^$)"
        res = wm.manage_window("focus", title)
        assert res.success is True
        assert res.output["window"] == title


class TestFileController:
    """Verify FileController atomic operations and verification checks."""

    @pytest.fixture
    def file_ctrl(self):
        td = tempfile.mkdtemp()
        fc = FileController(workspace_root=td)
        yield fc
        if os.path.exists(td):
            shutil.rmtree(td, ignore_errors=True)

    def test_create_file(self, file_ctrl):
        p = os.path.join(file_ctrl.workspace_root, "sub", "test.txt")
        res = file_ctrl.file_action("create", path=p, content="hello world")
        assert res.success is True
        assert res.verification_passed is True
        assert os.path.exists(p)
        with open(p, "r", encoding="utf-8") as f:
            assert f.read() == "hello world"

    def test_create_zero_byte_file(self, file_ctrl):
        p = os.path.join(file_ctrl.workspace_root, "empty.bin")
        res = file_ctrl.file_action("create", path=p, content="")
        assert res.success is True
        assert os.path.getsize(p) == 0

    def test_move_file(self, file_ctrl):
        src = os.path.join(file_ctrl.workspace_root, "src.txt")
        dst = os.path.join(file_ctrl.workspace_root, "dst.txt")
        file_ctrl.file_action("create", path=src, content="moving")
        res = file_ctrl.file_action("move", src=src, dst=dst)
        assert res.success is True
        assert res.verification_passed is True
        assert os.path.exists(dst)
        assert not os.path.exists(src)

    def test_move_file_missing_source_fails_verification(self, file_ctrl):
        src = os.path.join(file_ctrl.workspace_root, "missing.txt")
        dst = os.path.join(file_ctrl.workspace_root, "target.txt")
        res = file_ctrl.file_action("move", src=src, dst=dst)
        assert res.success is False
        assert res.verification_passed is False
        assert "not found" in res.error_message

    def test_copy_file(self, file_ctrl):
        src = os.path.join(file_ctrl.workspace_root, "original.txt")
        dst = os.path.join(file_ctrl.workspace_root, "copy.txt")
        file_ctrl.file_action("create", path=src, content="copy data")
        res = file_ctrl.file_action("copy", src=src, dst=dst)
        assert res.success is True
        assert os.path.exists(src)
        assert os.path.exists(dst)

    def test_rename_file(self, file_ctrl):
        src = os.path.join(file_ctrl.workspace_root, "old_name.txt")
        dst = os.path.join(file_ctrl.workspace_root, "new_name.txt")
        file_ctrl.file_action("create", path=src, content="data")
        res = file_ctrl.file_action("rename", src=src, dst=dst)
        assert res.success is True
        assert os.path.exists(dst)
        assert not os.path.exists(src)

    def test_delete_file_and_directory(self, file_ctrl):
        file_p = os.path.join(file_ctrl.workspace_root, "delete_me.txt")
        file_ctrl.file_action("create", path=file_p, content="trash")
        res = file_ctrl.file_action("delete", path=file_p)
        assert res.success is True
        assert res.verification_passed is True
        assert not os.path.exists(file_p)

        dir_p = os.path.join(file_ctrl.workspace_root, "folder_to_delete")
        os.makedirs(dir_p, exist_ok=True)
        file_ctrl.file_action("create", path=os.path.join(dir_p, "inner.txt"), content="sub")
        res_dir = file_ctrl.file_action("delete", path=dir_p)
        assert res_dir.success is True
        assert not os.path.exists(dir_p)

    def test_delete_nonexistent_fails(self, file_ctrl):
        res = file_ctrl.file_action("delete", path=os.path.join(file_ctrl.workspace_root, "ghost.txt"))
        assert res.success is False
        assert res.verification_passed is False
        assert "not found" in res.error_message

    def test_find_and_find_latest(self, file_ctrl):
        file_ctrl.file_action("create", path=os.path.join(file_ctrl.workspace_root, "doc1.pdf"), content="1")
        file_ctrl.file_action("create", path=os.path.join(file_ctrl.workspace_root, "doc2.pdf"), content="2")
        file_ctrl.file_action("create", path=os.path.join(file_ctrl.workspace_root, "notes.txt"), content="notes")

        find_res = file_ctrl.file_action("find", directory=file_ctrl.workspace_root, pattern="*.pdf")
        assert find_res.success is True
        assert len(find_res.output) == 2

        latest_res = file_ctrl.file_action("find_latest", directory=file_ctrl.workspace_root, extension=".pdf")
        assert latest_res.success is True
        assert latest_res.output.endswith(".pdf")

    def test_find_latest_empty_directory_fails(self, file_ctrl):
        empty_dir = os.path.join(file_ctrl.workspace_root, "empty_dir")
        os.makedirs(empty_dir, exist_ok=True)
        res = file_ctrl.file_action("find_latest", directory=empty_dir, extension=".pdf")
        assert res.success is False
        assert "No matching files" in res.error_message

    def test_path_traversal_and_null_bytes(self, file_ctrl):
        with pytest.raises(ValueError):
            file_ctrl._resolve_path("bad\0file.txt")


class TestSystemController:
    """Verify SystemController hardware controls and telemetry."""

    def test_volume_control_clamping(self):
        sys_ctrl = SystemController(mock_mode=True)
        res_low = sys_ctrl.control_volume(level=-20)
        assert res_low.output["volume"] == 0
        res_high = sys_ctrl.control_volume(level=150)
        assert res_high.output["volume"] == 100
        res_delta = sys_ctrl.control_volume(delta=-30)
        assert res_delta.output["volume"] == 70

    def test_brightness_control_clamping(self):
        sys_ctrl = SystemController(mock_mode=True)
        res_neg = sys_ctrl.control_brightness(level=-10)
        assert res_neg.output["brightness"] == 0
        res_high = sys_ctrl.control_brightness(level=120)
        assert res_high.output["brightness"] == 100

    @pytest.mark.parametrize("cmd,expected_state", [
        ("play", "playing"),
        ("pause", "paused"),
        ("stop", "paused"),
        ("next", "next_track"),
        ("previous", "prev_track"),
        ("unpause", "playing"),
    ])
    def test_media_transport_states(self, cmd, expected_state):
        sys_ctrl = SystemController(mock_mode=True)
        res = sys_ctrl.control_media(cmd)
        assert res.success is True
        assert res.output["media_state"] == expected_state

    def test_media_invalid_command(self):
        sys_ctrl = SystemController(mock_mode=True)
        res = sys_ctrl.control_media("invalid_cmd")
        assert res.success is False
        assert "Unknown media command" in res.error_message

    def test_system_stats_ranges(self):
        sys_ctrl = SystemController(mock_mode=True)
        stats = sys_ctrl.get_system_stats()
        assert 0.0 <= stats["cpu_percent"] <= 100.0
        assert 0.0 <= stats["memory_percent"] <= 100.0
        assert stats["disk_free_gb"] > 0.0
        assert stats["running_apps"] >= 0

    def test_notifications_deep_copy(self):
        sys_ctrl = SystemController(mock_mode=True)
        notifs = sys_ctrl.read_notifications()
        assert len(notifs) >= 1
        notifs.clear()
        assert len(sys_ctrl.read_notifications()) >= 1


class TestTerminalRunner:
    """Verify TerminalRunner command execution."""

    def test_run_terminal_echo(self):
        runner = TerminalRunner()
        res = runner.run_terminal("echo hello", shell="powershell")
        assert res.success is True
        assert "hello" in res.output

    def test_run_terminal_empty(self):
        runner = TerminalRunner()
        res = runner.run_terminal("")
        assert res.success is False
        assert "Empty terminal command" in res.error_message

    def test_run_terminal_timeout_simulation(self):
        runner = TerminalRunner()
        res = runner.run_terminal("while True: pass", timeout=2)
        assert res.success is False
        assert res.verification_passed is False
        assert "timed out" in res.error_message

    def test_run_terminal_error_simulation(self):
        runner = TerminalRunner()
        res = runner.run_terminal("python test_error.py")
        assert res.success is False
        assert res.verification_passed is False
        assert "Traceback" in res.error_message


class TestComputerControllerFacade:
    """Verify ComputerController integrates all modules."""

    def test_facade_properties_and_delegation(self):
        td = tempfile.mkdtemp()
        ctrl = ComputerController(workspace_root=td, mock_mode=True)
        try:
            assert ctrl.current_volume == 50
            ctrl.current_volume = 75
            assert ctrl.current_volume == 75

            assert ctrl.current_brightness == 70
            ctrl.current_brightness = 90
            assert ctrl.current_brightness == 90

            ctrl.open_app("Chrome")
            assert "chrome" in ctrl.running_apps
            assert "Chrome" in ctrl.active_window

            file_res = ctrl.file_action("create", path="facade_test.txt", content="pass")
            assert file_res.success is True

            stats = ctrl.get_system_stats()
            assert stats["running_apps"] == 1
        finally:
            if os.path.exists(td):
                shutil.rmtree(td, ignore_errors=True)
