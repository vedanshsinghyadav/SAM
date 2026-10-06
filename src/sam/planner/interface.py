"""
Task Planner Interface and Protocol Definitions for Project SAM.
Conforms to PROJECT.md line 210 and E2E harness Plan/PlanStep specifications.
Part of Milestone 5: FEAT-PLAN-001, FEAT-PLAN-002, FEAT-PLAN-003, FEAT-CTRL-009.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field

from src.sam.common.types import ToolCall


class PlanStep(BaseModel):
    """An atomic, ordered sub-task within an execution plan."""
    step_id: int = Field(..., description="1-indexed sequence ID of the step.")
    description: str = Field(..., description="Human-readable description of what this step does.")
    tool_call: ToolCall = Field(..., description="The tool invocation and arguments.")
    verification_criteria: str = Field(default="", description="Objective condition to confirm step success.")
    completed: bool = Field(default=False, description="Whether the step has completed execution.")
    result: Optional[str] = Field(default=None, description="Execution output or error string.")
    verification_passed: bool = Field(default=False, description="Whether post-step verification succeeded.")


class Plan(BaseModel):
    """Structured sequence of sub-tasks decomposing a high-level goal."""
    goal: str = Field(..., description="The user's original goal or command.")
    steps: List[PlanStep] = Field(default_factory=list, description="Ordered steps.")
    current_step_index: int = Field(default=0, description="Index of the currently active step.")
    is_completed: bool = Field(default=False, description="Whether all steps have executed successfully.")
    created_at: float = Field(default_factory=time.time, description="Creation timestamp.")


class PlanExecutionResult(BaseModel):
    """Overall outcome of executing a plan."""
    success: bool
    plan: Plan
    completed_steps: int
    error_message: Optional[str] = None


@runtime_checkable
class ITaskPlanner(Protocol):
    """Contract interface for goal decomposition, execution, and dynamic recovery."""

    def create_plan(self, goal: str) -> Plan:
        """Decompose a high-level goal into an ordered plan of atomic steps."""
        ...

    def execute_step(self, plan: Plan, step_index: int) -> PlanStep:
        """Execute a single step from the plan with safety and verification."""
        ...

    def execute_plan(self, plan: Plan) -> PlanExecutionResult:
        """Execute all remaining steps in the plan sequentially."""
        ...

    def recover_plan(self, plan: Plan, failed_step_index: int, error: str) -> Plan:
        """Dynamically adapt the plan when a step fails by inserting alternatives."""
        ...
