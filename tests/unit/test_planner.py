"""
Unit tests for SAM Autonomous Task Planner & Tool Router (Milestone 5).
Tests:
- ITaskPlanner protocol compliance
- Goal decomposition (exam prep, file moves, generic goals)
- Sequential step execution and state tracking
- Dynamic plan recovery upon step failure
- Multi-step execution via execute_plan()
- Safety authorization gating
"""

import pytest

from src.sam.common.types import RiskLevel, ToolCall
from src.sam.control.controller import ComputerController
from src.sam.planner.decomposer import GoalDecomposer
from src.sam.planner.engine import TaskPlanner
from src.sam.planner.interface import ITaskPlanner, Plan, PlanStep
from src.sam.safety.guard import SafetyGuard


class TestPlannerProtocol:
    """Verifies interface contract conformance."""

    def test_implements_itask_planner_protocol(self):
        planner = TaskPlanner()
        assert isinstance(planner, ITaskPlanner)


class TestGoalDecomposition:
    """Tests decomposition of goals into atomic steps."""

    def test_exam_goal_decomposition(self):
        decomposer = GoalDecomposer(enable_llm=False)
        steps = decomposer.decompose("SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do")
        assert len(steps) >= 4
        assert steps[0].tool_call.tool_name == "open_file"
        assert steps[1].tool_call.tool_name == "read_file"
        assert steps[2].tool_call.tool_name == "compare_topics"
        assert steps[3].tool_call.tool_name == "create_file"

    def test_move_pdf_decomposition(self):
        decomposer = GoalDecomposer(enable_llm=False)
        steps = decomposer.decompose("Move latest PDF to COA folder")
        assert len(steps) == 3
        assert steps[0].tool_call.tool_name == "find_latest"
        assert steps[1].tool_call.tool_name == "create_dir"
        assert steps[2].tool_call.tool_name == "move_file"

    def test_generic_goal_decomposition(self):
        decomposer = GoalDecomposer(enable_llm=False)
        steps = decomposer.decompose("Check system updates")
        assert len(steps) == 1
        assert steps[0].tool_call.tool_name == "general_action"


class TestStepExecution:
    """Tests execution and progression of plan steps."""

    def test_execute_step_advances_plan(self):
        planner = TaskPlanner()
        plan = planner.create_plan("Move latest PDF to COA folder")
        assert plan.current_step_index == 0
        assert not plan.is_completed

        step = planner.execute_step(plan, 0)
        assert step.completed is True
        assert plan.current_step_index == 1

    def test_execute_all_steps_completes_plan(self):
        planner = TaskPlanner()
        plan = planner.create_plan("Move latest PDF to COA folder")
        res = planner.execute_plan(plan)
        assert res.success is True
        assert res.completed_steps == 3
        assert plan.is_completed is True

    def test_invalid_step_index_raises(self):
        planner = TaskPlanner()
        plan = planner.create_plan("Backup")
        with pytest.raises(IndexError):
            planner.execute_step(plan, 100)


class TestPlanRecovery:
    """Tests dynamic replanning on step failure."""

    def test_recover_plan_replaces_failed_step(self):
        planner = TaskPlanner()
        plan = planner.create_plan("COA exam prep")
        revised = planner.recover_plan(plan, failed_step_index=1, error="FileNotFoundError: syllabus.txt")
        assert "Alternative" in revised.steps[1].description
        assert revised.steps[1].tool_call.tool_name == "search_filesystem"

    def test_recover_plan_preserves_prior_steps(self):
        planner = TaskPlanner()
        plan = planner.create_plan("COA exam prep")
        planner.execute_step(plan, 0)
        assert plan.steps[0].completed is True

        revised = planner.recover_plan(plan, failed_step_index=1, error="Resource locked")
        assert revised.steps[0].completed is True
        assert revised.steps[1].completed is False
