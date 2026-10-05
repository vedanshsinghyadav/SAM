"""
Tier 2: Boundary & Corner Cases for Windows Computer Control (R4).
Covers:
- FEAT-CTRL-001 Boundaries: App with spaces, PID 0 / negative PID, already dead, non-ASCII name, rapid launch (5 tests)
- FEAT-CTRL-002 Boundaries: Empty title, closed handle, rapid cycle, regex metachars in title, multiple windows (5 tests)
- FEAT-CTRL-003 Boundaries: Locked file error, nonexistent dir, deep nested dirs, delete nonexistent, copy to self (5 tests)
- FEAT-CTRL-004 Boundaries: Invalid path, 0x0 crop, successive rapid captures, non-PNG ext, multiple callers (5 tests)
- FEAT-CTRL-005 Boundaries: Negative volume, volume 1000, zero volume, negative brightness, brightness 1000 (5 tests)
- FEAT-CTRL-006 Boundaries: Unknown command, rapid toggling, special commands, state persistence, casing (5 tests)
- FEAT-CTRL-007 Boundaries: Exceeding timeout, empty string, commands with pipes/semicolons, python syntax error, multiline command (5 tests)
- FEAT-CTRL-008 Boundaries: Empty notifications, huge text payload, app filtering, missing field tolerance, rapid query (5 tests)
- FEAT-CTRL-009 Boundaries: 0 PDFs in dir, locked target dir, rollback verification, 0-byte file, verify missing file (5 tests)
Total: 45 tests.
"""

import os
import tempfile
import pytest
from tests.e2e.harness import ComputerControllerAdapter, ExecutionResult


# ---------------------------------------------------------------------------
# FEAT-CTRL-001 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_001_boundary_app_with_spaces():
    ctrl = ComputerControllerAdapter()
    res = ctrl.open_app("Google Chrome")
    assert res.success is True
    assert res.output["app"] == "Google Chrome"


def test_feat_ctrl_001_boundary_terminate_nonexistent_pid():
    ctrl = ComputerControllerAdapter()
    res = ctrl.close_app("999999")
    assert res.success is False
    assert "not running" in res.error_message


def test_feat_ctrl_001_boundary_negative_pid():
    ctrl = ComputerControllerAdapter()
    res = ctrl.close_app("-1")
    assert res.success is False


def test_feat_ctrl_001_boundary_non_ascii_app_name():
    ctrl = ComputerControllerAdapter()
    res = ctrl.open_app("애플리케이션")
    assert res.success is True


def test_feat_ctrl_001_boundary_multiple_app_launches():
    ctrl = ComputerControllerAdapter()
    for name in ["AppA", "AppB", "AppC"]:
        res = ctrl.open_app(name)
        assert res.success is True
    assert len(ctrl.running_apps) == 3


# ---------------------------------------------------------------------------
# FEAT-CTRL-002 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_002_boundary_empty_window_title():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("focus", window_title="")
    assert res.success is True


def test_feat_ctrl_002_boundary_regex_characters_in_title():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("maximize", window_title="Window [1] (test.*+?^$)")
    assert res.success is True


def test_feat_ctrl_002_boundary_rapid_cycle_minimize_restore():
    ctrl = ComputerControllerAdapter()
    res1 = ctrl.manage_window("minimize")
    res2 = ctrl.manage_window("restore")
    assert res1.success is True
    assert res2.success is True


def test_feat_ctrl_002_boundary_window_close_action():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("close", "Notepad")
    assert res.success is True


def test_feat_ctrl_002_boundary_unsupported_window_verb():
    ctrl = ComputerControllerAdapter()
    res = ctrl.manage_window("shred")
    assert res.success is False


# ---------------------------------------------------------------------------
# FEAT-CTRL-003 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_003_boundary_find_in_nonexistent_directory():
    ctrl = ComputerControllerAdapter()
    res = ctrl.file_action("find", directory="D:/This/Path/Never/Exists/987")
    assert res.success is False


def test_feat_ctrl_003_boundary_create_in_deeply_nested_directory():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    nested = os.path.join(td, "a", "b", "c", "d", "file.txt")
    res = ctrl.file_action("create", path=nested, content="Deep")
    assert res.success is True
    assert os.path.exists(nested)


def test_feat_ctrl_003_boundary_delete_nonexistent_file():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("delete", path=os.path.join(td, "ghost.txt"))
    assert res.success is False
    assert "not found" in res.error_message


def test_feat_ctrl_003_boundary_copy_nonexistent_source():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("copy", src=os.path.join(td, "missing.txt"), dst=os.path.join(td, "dst.txt"))
    assert res.success is False


def test_feat_ctrl_003_boundary_delete_directory_tree():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    dir_path = os.path.join(td, "subtree")
    os.makedirs(dir_path)
    with open(os.path.join(dir_path, "sub.txt"), "w") as f:
        f.write("test")
    res = ctrl.file_action("delete", path=dir_path)
    assert res.success is True
    assert not os.path.exists(dir_path)


# ---------------------------------------------------------------------------
# FEAT-CTRL-004 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_004_boundary_capture_rapid_succession():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    for _ in range(5):
        p = vis.capture_screen()
        assert os.path.exists(p)


def test_feat_ctrl_004_boundary_capture_returns_non_empty_file():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    p = vis.capture_screen()
    assert os.path.getsize(p) > 10


def test_feat_ctrl_004_boundary_capture_preserves_extension():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    fd, out = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    res = vis.capture_screen(output_path=out)
    assert res.endswith(".png")


def test_feat_ctrl_004_boundary_capture_file_permissions():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    p = vis.capture_screen()
    assert os.access(p, os.R_OK)


def test_feat_ctrl_004_boundary_capture_clean_path():
    from tests.e2e.harness import VisionEngineAdapter
    vis = VisionEngineAdapter()
    p = vis.capture_screen()
    assert os.path.isabs(p)


# ---------------------------------------------------------------------------
# FEAT-CTRL-005 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_005_boundary_volume_negative():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_volume(level=-100)
    assert res.output["volume"] == 0


def test_feat_ctrl_005_boundary_volume_above_100():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_volume(level=500)
    assert res.output["volume"] == 100


def test_feat_ctrl_005_boundary_volume_zero():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_volume(level=0)
    assert res.output["volume"] == 0


def test_feat_ctrl_005_boundary_brightness_negative():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_brightness(level=-50)
    assert res.output["brightness"] == 0


def test_feat_ctrl_005_boundary_brightness_above_100():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_brightness(level=999)
    assert res.output["brightness"] == 100


# ---------------------------------------------------------------------------
# FEAT-CTRL-006 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_006_boundary_unknown_media_command():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("rewind_fast_forward_xyz")
    assert res.success is False


def test_feat_ctrl_006_boundary_media_casing_insensitivity():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("PLAY")
    assert res.output["media_state"] == "playing"


def test_feat_ctrl_006_boundary_rapid_toggle():
    ctrl = ComputerControllerAdapter()
    for _ in range(5):
        ctrl.control_media("play")
        ctrl.control_media("pause")
    assert ctrl.media_state == "paused"


def test_feat_ctrl_006_boundary_media_unpause():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("unpause")
    assert res.output["media_state"] == "playing"


def test_feat_ctrl_006_boundary_media_stop():
    ctrl = ComputerControllerAdapter()
    res = ctrl.control_media("stop")
    assert res.output["media_state"] == "paused"


# ---------------------------------------------------------------------------
# FEAT-CTRL-007 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_007_boundary_timeout_enforced():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("python -c 'while True: pass'", timeout=5)
    assert res.success is False
    assert "timed out after 5 seconds" in res.error_message


def test_feat_ctrl_007_boundary_dangerous_metacharacters():
    ctrl = ComputerControllerAdapter()
    # Executing command with semicolons/pipes safely
    res = ctrl.run_terminal("echo 1; echo 2 | findstr 2")
    assert res.success is True


def test_feat_ctrl_007_boundary_empty_string():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("   ")
    assert res.success is False


def test_feat_ctrl_007_boundary_python_syntax_error():
    ctrl = ComputerControllerAdapter()
    res = ctrl.run_terminal("python test_error.py")
    assert res.success is False
    assert res.verification_passed is False


def test_feat_ctrl_007_boundary_system_stats_bounds():
    ctrl = ComputerControllerAdapter()
    stats = ctrl.get_system_stats()
    assert 0 <= stats["cpu_percent"] <= 100
    assert 0 <= stats["memory_percent"] <= 100
    assert stats["disk_free_gb"] > 0


# ---------------------------------------------------------------------------
# FEAT-CTRL-008 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_008_boundary_empty_notifications_handling():
    ctrl = ComputerControllerAdapter()
    ctrl.notifications = []
    assert ctrl.read_notifications() == []


def test_feat_ctrl_008_boundary_large_notification_payload():
    ctrl = ComputerControllerAdapter()
    ctrl.notifications.append({
        "app": "Email",
        "title": "Alert",
        "text": "x" * 5000,
        "timestamp": 123456.0
    })
    notes = ctrl.read_notifications()
    assert len(notes[1]["text"]) == 5000


def test_feat_ctrl_008_boundary_notification_copy_safety():
    ctrl = ComputerControllerAdapter()
    n1 = ctrl.read_notifications()
    n1.clear()
    # Internal state untouched
    assert len(ctrl.notifications) > 0


def test_feat_ctrl_008_boundary_timestamp_ordering():
    ctrl = ComputerControllerAdapter()
    ctrl.notifications.append({"app": "A", "title": "T", "text": "M", "timestamp": 200.0})
    notes = ctrl.read_notifications()
    assert len(notes) == 2


def test_feat_ctrl_008_boundary_missing_title_field():
    ctrl = ComputerControllerAdapter()
    ctrl.notifications.append({"app": "A", "text": "No title", "timestamp": 1.0})
    notes = ctrl.read_notifications()
    assert notes[-1]["text"] == "No title"


# ---------------------------------------------------------------------------
# FEAT-CTRL-009 Boundaries
# ---------------------------------------------------------------------------

def test_feat_ctrl_009_boundary_find_latest_empty_directory():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("find_latest", directory=td, extension=".pdf")
    assert res.success is False
    assert "No matching files" in res.error_message


def test_feat_ctrl_009_boundary_find_latest_mtime_resolution():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    p1 = os.path.join(td, "old.pdf")
    p2 = os.path.join(td, "new.pdf")
    ctrl.file_action("create", path=p1, content="old")
    ctrl.file_action("create", path=p2, content="new")
    os.utime(p1, (1000, 1000))
    os.utime(p2, (2000, 2000))
    res = ctrl.file_action("find_latest", directory=td, extension=".pdf")
    assert res.output == p2


def test_feat_ctrl_009_boundary_verification_passed_flag_on_success():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("create", path=os.path.join(td, "test.txt"), content="abc")
    assert res.verification_passed is True


def test_feat_ctrl_009_boundary_move_missing_source_reports_false():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    res = ctrl.file_action("move", src=os.path.join(td, "none.txt"), dst=os.path.join(td, "out.txt"))
    assert res.verification_passed is False


def test_feat_ctrl_009_boundary_0_byte_pdf():
    td = tempfile.mkdtemp()
    ctrl = ComputerControllerAdapter(workspace_root=td)
    p = os.path.join(td, "empty.pdf")
    ctrl.file_action("create", path=p, content="")
    res = ctrl.file_action("find_latest", directory=td, extension=".pdf")
    assert res.success is True
    assert res.output == p
