"""
Test fixtures, mock environments, and temporary filesystem helpers for Project SAM E2E tests.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Generator
from tests.e2e.harness import SAMSystemFacade, ComputerControllerAdapter, MemoryEngineAdapter


class TempWorkspace:
    """Creates a temporary isolated filesystem simulating Windows user directories."""
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="sam_test_workspace_")
        self.downloads_dir = os.path.join(self.root, "Downloads")
        self.notes_dir = os.path.join(self.root, "Notes")
        self.coa_dir = os.path.join(self.notes_dir, "COA")
        self.projects_dir = os.path.join(self.root, "Projects", "SAM")

        os.makedirs(self.downloads_dir, exist_ok=True)
        os.makedirs(self.coa_dir, exist_ok=True)
        os.makedirs(self.projects_dir, exist_ok=True)

        self._populate_initial_files()

    def _populate_initial_files(self):
        # Sample PDF in downloads
        pdf_path = os.path.join(self.downloads_dir, "lecture_notes_chapter1.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 Mock PDF content for testing")

        # Sample COA notes in Notes/COA
        notes_path = os.path.join(self.coa_dir, "coa_unit1.txt")
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write("COA Unit 1: Pipelining, Hazards, and Cache Memory Architecture")

        # Sample syllabus file
        syllabus_path = os.path.join(self.coa_dir, "syllabus.txt")
        with open(syllabus_path, "w", encoding="utf-8") as f:
            f.write("Syllabus: Unit 1: Pipelining, Unit 2: Cache, Unit 3: Virtual Memory, Unit 4: Multiprocessors")

        # Sample python script
        py_path = os.path.join(self.root, "test_script.py")
        with open(py_path, "w", encoding="utf-8") as f:
            f.write("print('Hello from test script')\n")

    def create_dummy_pdf(self, name: str, mtime_offset: int = 0) -> str:
        path = os.path.join(self.downloads_dir, name)
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 Mock test PDF")
        if mtime_offset != 0:
            mtime = os.path.getmtime(path) + mtime_offset
            os.utime(path, (mtime, mtime))
        return path

    def cleanup(self):
        if os.path.exists(self.root):
            try:
                shutil.rmtree(self.root, ignore_errors=True)
            except Exception:
                pass


def create_test_system(workspace_root: str = None) -> SAMSystemFacade:
    """Helper factory for a fresh SAMSystemFacade."""
    return SAMSystemFacade(workspace_root=workspace_root)
