"""
Generates a native Windows desktop shortcut (.lnk) for the SAM Desktop GUI.
Target: pythonw.exe (hidden console, pure GUI mode)
"""

import os
import subprocess
import sys


def create_desktop_shortcut():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pythonw_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Python\bin\pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")

    user_profile = os.environ.get("USERPROFILE", "")
    desktop = os.path.join(user_profile, "Desktop")
    if not os.path.exists(desktop):
        print(f"Desktop not found at {desktop}")
        return False

    shortcut_path = os.path.join(desktop, "SAM AI.lnk")
    temp_vbs = os.path.join(repo_dir, "_temp_shortcut.vbs")

    vbs_content = f'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{pythonw_path}"
oLink.Arguments = "-m src.sam.gui.app"
oLink.WorkingDirectory = "{repo_dir}"
oLink.Description = "SAM - JARVIS AI Assistant"
oLink.Save
'''

    try:
        with open(temp_vbs, "w", encoding="utf-8") as f:
            f.write(vbs_content)

        subprocess.run(["cscript", "//Nologo", temp_vbs], check=True, capture_output=True)
        if os.path.exists(shortcut_path):
            print(f"[SUCCESS] Desktop shortcut created: {shortcut_path}")
            return True
        else:
            print("[WARNING] Shortcut file not found after generation.")
            return False
    finally:
        if os.path.exists(temp_vbs):
            os.remove(temp_vbs)


if __name__ == "__main__":
    create_desktop_shortcut()
