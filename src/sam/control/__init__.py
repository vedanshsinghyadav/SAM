"""
SAM Windows Control Suite.
Exports ComputerController, ExecutionResult, and IComputerController protocol.
"""

from src.sam.common.types import ExecutionResult
from src.sam.control.interface import IComputerController
from src.sam.control.controller import ComputerController

__all__ = [
    "ComputerController",
    "ExecutionResult",
    "IComputerController",
]
