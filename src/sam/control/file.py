"""
Atomic File Automation Engine with Path Traversal Protection.
Handles find, find_latest, create, move, copy, rename, delete with verification guarantees.
"""

from __future__ import annotations
import glob
import os
import shutil
import tempfile
from typing import List, Optional
from src.sam.common.types import ExecutionResult


class FileController:
    """Provides verified atomic filesystem operations."""

    def __init__(self, workspace_root: Optional[str] = None, allowed_roots: Optional[List[str]] = None):
        self.workspace_root = os.path.abspath(workspace_root or tempfile.gettempdir())
        os.makedirs(self.workspace_root, exist_ok=True)
        # Pre-create standard workspace folders for scenarios
        os.makedirs(os.path.join(self.workspace_root, "Downloads"), exist_ok=True)
        self.allowed_roots = [os.path.abspath(r) for r in allowed_roots] if allowed_roots else None

    def _resolve_path(self, path: str) -> str:
        """Sanitizes path, handles relative workspace resolution, and prevents traversal escapes."""
        if "\0" in path:
            raise ValueError("Null byte injection detected in path")

        if not os.path.isabs(path):
            candidate = os.path.join(self.workspace_root, path)
        else:
            candidate = path

        resolved = os.path.abspath(os.path.normpath(candidate))

        if self.allowed_roots:
            if not any(resolved.startswith(r) for r in self.allowed_roots):
                raise PermissionError(f"Path '{resolved}' outside authorized directories")

        return resolved

    def file_action(self, action: str, **kwargs) -> ExecutionResult:
        """Unified file action dispatcher with atomic verification."""
        act = action.strip().lower()
        try:
            if act == "find":
                directory = kwargs.get("directory", self.workspace_root)
                clean_dir = self._resolve_path(directory)
                pattern = kwargs.get("pattern", "*")
                if not os.path.exists(clean_dir):
                    return ExecutionResult(
                        success=False,
                        output=[],
                        error_message=f"Directory '{directory}' does not exist",
                        verification_passed=False,
                    )
                matches = glob.glob(os.path.join(clean_dir, pattern))
                return ExecutionResult(success=True, output=matches, verification_passed=True)

            elif act == "find_latest":
                directory = kwargs.get("directory", self.workspace_root)
                clean_dir = self._resolve_path(directory)
                extension = kwargs.get("extension", ".pdf")
                if not os.path.exists(clean_dir):
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message=f"Directory '{directory}' not found",
                        verification_passed=False,
                    )
                candidates = [
                    os.path.join(clean_dir, f)
                    for f in os.listdir(clean_dir)
                    if f.lower().endswith(extension.lower())
                ]
                if not candidates:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message=f"No matching files with extension '{extension}'",
                        verification_passed=False,
                    )
                latest = max(candidates, key=os.path.getmtime)
                return ExecutionResult(success=True, output=latest, verification_passed=True)

            elif act == "create":
                path = kwargs.get("path")
                content = kwargs.get("content", "")
                if not path:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message="Path required",
                        verification_passed=False,
                    )
                clean_path = self._resolve_path(path)
                os.makedirs(os.path.dirname(clean_path), exist_ok=True)
                # Atomic write via temp file
                tmp_path = clean_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, clean_path)
                return ExecutionResult(
                    success=True,
                    output=clean_path,
                    verification_passed=os.path.exists(clean_path),
                )

            elif act == "move":
                src = kwargs.get("src")
                dst = kwargs.get("dst")
                if not src or not dst:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message="Source and destination required",
                        verification_passed=False,
                    )
                clean_src = self._resolve_path(src)
                clean_dst = self._resolve_path(dst)
                if not os.path.exists(clean_src):
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message=f"Source file '{src}' not found",
                        verification_passed=False,
                    )
                os.makedirs(os.path.dirname(clean_dst), exist_ok=True)
                shutil.move(clean_src, clean_dst)
                verified = os.path.exists(clean_dst) and not os.path.exists(clean_src)
                return ExecutionResult(
                    success=True,
                    output=clean_dst,
                    verification_passed=verified,
                )

            elif act == "copy":
                src = kwargs.get("src")
                dst = kwargs.get("dst")
                if not src or not dst:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message="Source and destination required",
                        verification_passed=False,
                    )
                clean_src = self._resolve_path(src)
                clean_dst = self._resolve_path(dst)
                if not os.path.exists(clean_src):
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message=f"Source '{src}' not found",
                        verification_passed=False,
                    )
                os.makedirs(os.path.dirname(clean_dst), exist_ok=True)
                if os.path.isdir(clean_src):
                    shutil.copytree(clean_src, clean_dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(clean_src, clean_dst)
                return ExecutionResult(
                    success=True,
                    output=clean_dst,
                    verification_passed=os.path.exists(clean_dst),
                )

            elif act == "rename":
                src = kwargs.get("src") or kwargs.get("path")
                dst = kwargs.get("dst") or kwargs.get("new_path")
                if not src or not dst:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message="Valid source and destination required",
                        verification_passed=False,
                    )
                clean_src = self._resolve_path(src)
                clean_dst = self._resolve_path(dst)
                if not os.path.exists(clean_src):
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message="Valid source and destination required",
                        verification_passed=False,
                    )
                os.makedirs(os.path.dirname(clean_dst), exist_ok=True)
                os.replace(clean_src, clean_dst)
                return ExecutionResult(
                    success=True,
                    output=clean_dst,
                    verification_passed=os.path.exists(clean_dst),
                )

            elif act == "delete":
                path = kwargs.get("path")
                if not path:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message="Path required",
                        verification_passed=False,
                    )
                clean_path = self._resolve_path(path)
                if not os.path.exists(clean_path):
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error_message=f"Path '{path}' not found",
                        verification_passed=False,
                    )
                if os.path.isdir(clean_path):
                    shutil.rmtree(clean_path)
                else:
                    os.remove(clean_path)
                verified = not os.path.exists(clean_path)
                return ExecutionResult(
                    success=True,
                    output=clean_path,
                    verification_passed=verified,
                )

            return ExecutionResult(
                success=False,
                output=None,
                error_message=f"Unknown file action: {action}",
                verification_passed=False,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error_message=str(e),
                verification_passed=False,
            )
