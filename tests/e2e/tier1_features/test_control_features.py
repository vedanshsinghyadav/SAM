"""
Tier 1: Feature Coverage Tests for Windows Computer Control (R4).
Covers:
- FEAT-CTRL-001: Windows App Lifecycle (5 tests)
- FEAT-CTRL-002: Windows Window Manager (5 tests)
- FEAT-CTRL-003: File Automation Engine (5 tests)
- FEAT-CTRL-004: Desktop Screen Capture (5 tests)
- FEAT-CTRL-005: Volume & Brightness Control (5 tests)
- FEAT-CTRL-006: Media Playback Controller (5 tests)
- FEAT-CTRL-007: Terminal Command Runner (5 tests)
- FEAT-CTRL-008: Windows Notification Reader (5 tests)
- FEAT-CTRL-009: Atomic Sequential Verify (5 tests)
Total: 45 tests.
"""

import os
import tempfile
import pytest
from tests.e2e.harness import ComputerControllerAdapter


# ---------------------------------------------------------------------------
# FEAT-CTRL-001: Windows App Lifecycle
# ---------------------------------------------------------------------------

def test_feat_ctrl_001_open_app_returns_success_and_pid():
    ctrl = ComputerControllerAdapter()
    res = ctrl.open_app("Chrome")
    assert res.success is True
    assert "pid" in res.output
    assert res.output["app"] == "Chrome"


def test_feat_ctrl_001_close_app_by_name():
    ctrl = ComputerControllerAdapter()
    ctrl.open_app("Spotify")
    res = ctrl.close_app("Spotify")
    assert res.success is True
    assert res.output["app"] == "Spotify"


def test_feat_ctrl_001_close_app_by_pid():
    ctrl = ComputerControllerAdapter()
    open_res = ctrl.open_app("Notepad")
    pid = open_res.output["pid"]
    close_res = ctrl.close_app(str(pid))
    assert close_res.success is True


def test_feat_ctrl_001_close_unopened_app_fails():
    ctrl = ComputerControllerAdapter()
    res = ctrl.close_app("NonExistentApp123")
    assert res.success is False
    assert "not running" in res.error_message


def test_feat_ctrl_001_open_empty_app_name_fails():
    ctrl = ComputerControllerAdapter()
    res = ctrl.open_app("")
    assert res.success is False


# ---------------------------------------------------------------------------
# FEAT-CTRL-002: Windows Window Manager
# ---------------------------------------------------------------------------

def test_feat_ctrl_002_manage_window_focus():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("focus", "Chrome")
    assert res.success is True
    assert res.output["action"] == "focus"


def test_feat_ctrl_002_manage_window_maximize():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("maximize")
    assert res.success is True
    assert res.output["action"] == "maximize"


def test_feat_ctrl_002_manage_window_minimize():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("minimize")
    assert res.success is True
    assert res.output["action"] == "minimize"


def test_feat_ctrl_002_manage_window_restore():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("restore")
    assert res.success is True
    assert res.output["action"] == "restore"


def test_feat_ctrl_002_manage_window_invalid_action():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("explode")
    assert res.success is False
    assert "Unknown window action" in res.error_message


# ---------------------------------------------------------------------------
# FEAT-CTRL-003: File Automation Engine
# ---------------------------------------------------------------------------

def test_feat_ctrl_003_create_file():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    path = os.path.join(td, "hello.txt")
    res = ctrl.file_action("create", path=path, content="Hello World")
    assert res.success is True
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        assert f.read() == "Hello World"


def test_feat_ctrl_003_move_file():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    src = os.path.join(td, "source.txt")
    dst = os.path.join(td, "dest.txt")
    ctrl.file_action("create", path=src, content="Move me")
    res = ctrl.file_action("move", src=src, dst=dst)
    assert res.success is True
    assert os.path.exists(dst)
    assert not os.path.exists(src)


def test_feat_ctrl_003_copy_file():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    src = os.path.join(td, "original.txt")
    dst = os.path.join(td, "copy.txt")
    ctrl.file_action("create", path=src, content="Copy me")
    res = ctrl.file_action("copy", src=src, dst=dst)
    assert res.success is True
    assert os.path.exists(src)
    assert os.path.exists(dst)


def test_feat_ctrl_003_delete_file():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    target = os.path.join(td, "trash.txt")
    ctrl.file_action("create", path=target, content="Trash")
    res = ctrl.file_action("delete", path=target)
    assert res.success is True
    assert not os.path.exists(target)


def test_feat_ctrl_003_find_files():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    ctrl.file_action("create", path=os.path.join(td, "a.pdf"), content="1")
    ctrl.file_action("create", path=os.path.join(td, "b.txt"), content="2")
    res = ctrl.file_action("find", directory=td, pattern="*.pdf")
    assert res.success is True
    assert len(res.output) == 1
    assert res.output[0].endswith("a.pdf")


# ---------------------------------------------------------------------------
# FEAT-CTRL-004: Desktop Screen Capture
# ---------------------------------------------------------------------------

def test_feat_ctrl_004_capture_screen_returns_path():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    path = vis.capture_screen()
    assert os.path.exists(path)
    assert path.endswith(".png")


def test_feat_ctrl_004_capture_screen_valid_png_header():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    path = vis.capture_screen()
    with open(path, "rb") as f:
        header = f.read(8)
    assert header == b"\x89PNG\r\n\x1a\n"


def test_feat_ctrl_004_capture_screen_custom_output_path():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    fd, out = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    path = vis.capture_screen(output_path=out)
    assert path == out
    assert os.path.getsize(path) > 0


def test_feat_ctrl_004_capture_screen_idempotent():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    p1 = vis.capture_screen()
    p2 = vis.capture_screen()
    assert os.path.exists(p1)
    assert os.path.exists(p2)
    assert p1 != p2


def test_feat_ctrl_004_capture_non_empty_bytes():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    path = vis.capture_screen()
    assert os.path.getsize(path) > 20


# ---------------------------------------------------------------------------
# FEAT-CTRL-005: Volume & Brightness Control
# ---------------------------------------------------------------------------

def test_feat_ctrl_005_set_volume():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_volume(level=80)
    assert res.success is True
    assert res.output["volume"] == 80


def test_feat_ctrl_005_delta_volume():
    ctrl = ComputerControllerAdapter()
    ctrl.control_volume(level=50)
    res = ctrl.control_volume(delta=+15)
    assert res.output["volume"] == 65


def test_feat_ctrl_005_volume_clamping():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_volume(level=150)
    assert res.output["volume"] == 100
    res_min = ctrl.control_volume(level=-20)
    assert res_min.output["volume"] == 0


def test_feat_ctrl_005_set_brightness():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_brightness(level=90)
    assert res.success is True
    assert res.output["brightness"] == 90


def test_feat_ctrl_005_brightness_clamping():
    ctrl = ComputerControllerAdapter()
    res_high = ctrl.control_brightness(level=200)
    assert res_high.output["brightness"] == 100
    res_low = ctrl.control_brightness(level=-50)
    assert res_low.output["brightness"] == 0


# ---------------------------------------------------------------------------
# FEAT-CTRL-006: Media Playback Controller
# ---------------------------------------------------------------------------

def test_feat_ctrl_006_media_play():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("play")
    assert res.success is True
    assert res.output["media_state"] == "playing"


def test_feat_ctrl_006_media_pause():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("pause")
    assert res.success is True
    assert res.output["media_state"] == "paused"


def test_feat_ctrl_006_media_next():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("next")
    assert res.success is True
    assert res.output["media_state"] == "next_track"


def test_feat_ctrl_006_media_prev():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("previous")
    assert res.success is True
    assert res.output["media_state"] == "prev_track"


def test_feat_ctrl_006_invalid_media_command():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("invalid_action")
    assert res.success is False


# ---------------------------------------------------------------------------
# FEAT-CTRL-007: Terminal Command Runner
# ---------------------------------------------------------------------------

def test_feat_ctrl_007_run_command_success():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("echo 'hello'")
    assert res.success is True
    assert res.verification_passed is True


def test_feat_ctrl_007_run_empty_command_fails():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("")
    assert res.success is False
    assert "Empty terminal command" in res.error_message


def test_feat_ctrl_007_run_command_timeout():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("python -c 'while True: pass'", timeout=10)
    assert res.success is False
    assert "timed out" in res.error_message


def test_feat_ctrl_007_run_python_script_error():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("python test_error.py")
    assert res.success is False
    assert "Traceback" in res.error_message


def test_feat_ctrl_007_powershell_shell_parameter():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("Get-Process", shell="powershell")
    assert res.success is True


# ---------------------------------------------------------------------------
# FEAT-CTRL-008: Windows Notification Reader
# ---------------------------------------------------------------------------

def test_feat_ctrl_008_reads_notifications_list():
    ctrl = ComputerControllerAdapter()
    notes = ctrl.read_notifications()
    assert isinstance(notes, list)
    assert len(notes) > 0


def test_feat_ctrl_008_notification_data_fields():
    ctrl = ComputerControllerAdapter()
    note = ctrl.read_notifications()[0]
    assert "app" in note
    assert "title" in note
    assert "text" in note
    assert "timestamp" in note


def test_feat_ctrl_008_notification_app_name():
    ctrl = ComputerControllerAdapter()
    note = ctrl.read_notifications()[0]
    assert note["app"] == "Slack"


def test_feat_ctrl_008_notification_timestamp():
    ctrl = ComputerControllerAdapter()
    note = ctrl.read_notifications()[0]
    assert note["timestamp"] > 0


def test_feat_ctrl_008_notification_text_content():
    ctrl = ComputerControllerAdapter()
    note = ctrl.read_notifications()[0]
    assert len(note["text"]) > 0


# ---------------------------------------------------------------------------
# FEAT-CTRL-009: Atomic Sequential Verify
# ---------------------------------------------------------------------------

def test_feat_ctrl_009_find_latest_pdf():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    ctrl.file_action("create", path=os.path.join(td, "doc1.pdf"), content="1")
    ctrl.file_action("create", path=os.path.join(td, "doc2.pdf"), content="2")
    res = ctrl.file_action("find_latest", directory=td, extension=".pdf")
    assert res.success is True
    assert res.output.endswith("doc2.pdf") or res.output.endswith("doc1.pdf")


def test_feat_ctrl_009_verify_move_destination_exists():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    src = os.path.join(td, "a.pdf")
    dst = os.path.join(td, "b.pdf")
    ctrl.file_action("create", path=src, content="PDF data")
    res = ctrl.file_action("move", src=src, dst=dst)
    assert res.success is True
    assert res.verification_passed is True
    assert os.path.exists(dst)


def test_feat_ctrl_009_verify_delete_target_removed():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    path = os.path.join(td, "temp.txt")
    ctrl.file_action("create", path=path, content="x")
    res = ctrl.file_action("delete", path=path)
    assert res.success is True
    assert res.verification_passed is True
    assert not os.path.exists(path)


def test_feat_ctrl_009_missing_file_reports_verification_failure():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("move", src=os.path.join(td, "missing.txt"), dst=os.path.join(td, "dst.txt"))
    assert res.success is False
    assert "not found" in res.error_message


def test_feat_ctrl_009_find_latest_on_empty_dir_fails_gracefully():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("find_latest", directory=td, extension=".pdf")
    assert res.success is False
    assert "No matching files" in res.error_message
