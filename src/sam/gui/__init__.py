"""
SAM GUI Desktop Application Package.
Provides a modern native Windows GUI interface for Project SAM without requiring CMD or terminal.
"""

from src.sam.gui.app import SAMGuiApp, run_gui

__all__ = ["SAMGuiApp", "run_gui"]
