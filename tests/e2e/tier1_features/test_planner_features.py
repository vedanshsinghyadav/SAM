"""
Tier 1: Feature Coverage Tests for Autonomous Task Planner & Router (R6).
Covers:
- FEAT-PLAN-001: Goal Decomposition Planner (5 tests)
- FEAT-PLAN-002: Dynamic Multi-Tool Router (5 tests)
- FEAT-PLAN-003: Plan Recovery & Resilience (5 tests)
Total: 15 tests.
"""

import pytest
from tests.e2e.harness import (
    TaskPlannerAdapter, ComputerControllerAdapter, SafetyGuardAdapter,
    ToolCall, Plan
)


# ---------------------------------------------------------------------------
# FEAT-PLAN-001: Goal Decomposition Planner
# ---------------------------------------------------------------------------

def test_feat_plan_001_exam_goal_decomposes_to_multiple_steps():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("SAM, kal COA exam hai. Notes kholo, syllabus check karo, missing topics ki list bana do")
    assert len(plan.steps) >= 4
    assert plan.is_completed is False


def test_feat_plan_001_ordered_step_ids():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("COA exam prep")
    step_ids = [s.step_id for s in plan.steps]
    assert step_ids == list(range(1, len(plan.steps) + 1))


def test_feat_plan_001_steps_contain_verification_criteria():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("COA exam prep")
    for s in plan.steps:
        assert len(s.verification_criteria) > 0


def test_feat_plan_001_simple_action_decomposition():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Backup configuration")
    assert len(plan.steps) >= 1
    assert plan.steps[0].tool_call.tool_name == "general_action"


def test_feat_plan_001_move_pdf_decomposition():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Move latest PDF to COA folder")
    assert len(plan.steps) == 3
    assert plan.steps[0].tool_call.tool_name == "find_latest"
    assert plan.steps[2].tool_call.tool_name == "move_file"


# ---------------------------------------------------------------------------
# FEAT-PLAN-002: Dynamic Multi-Tool Router
# ---------------------------------------------------------------------------

def test_feat_plan_002_routes_file_tool():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Move latest PDF to COA")
    assert any(s.tool_call.tool_name == "find_latest" for s in plan.steps)


def test_feat_plan_002_routes_system_tool():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    step = planner.execute_step(planner.create_plan("Test goal"), 0)
    assert step.completed is True


def test_feat_plan_002_step_advances_plan_index():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Move latest PDF to COA")
    assert plan.current_step_index == 0
    planner.execute_step(plan, 0)
    assert plan.current_step_index == 1


def test_feat_plan_002_plan_completes_when_all_steps_done():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Backup")
    assert not plan.is_completed
    planner.execute_step(plan, 0)
    assert plan.is_completed is True


def test_feat_plan_002_invalid_step_index_raises():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Test")
    with pytest.raises(IndexError):
        planner.execute_step(plan, 999)


# ---------------------------------------------------------------------------
# FEAT-PLAN-003: Plan Recovery & Resilience
# ---------------------------------------------------------------------------

def test_feat_plan_003_recover_plan_replaces_failed_step():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("COA exam prep")
    revised = planner.recover_plan(plan, failed_step_index=1, error="FileNotFoundError: syllabus.txt")
    assert "Alternative" in revised.steps[1].description
    assert revised.steps[1].tool_call.tool_name == "search_filesystem"


def test_feat_plan_003_preserves_prior_completed_steps():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("COA exam prep")
    planner.execute_step(plan, 0)
    assert plan.steps[0].completed is True
    revised = planner.recover_plan(plan, failed_step_index=1, error="File missing")
    assert revised.steps[0].completed is True


def test_feat_plan_003_recovery_includes_error_in_description():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("COA exam prep")
    revised = planner.recover_plan(plan, failed_step_index=0, error="PermissionDenied")
    assert "PermissionDenied" in revised.steps[0].description


def test_feat_plan_003_recovered_step_can_be_executed():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("COA exam prep")
    planner.recover_plan(plan, failed_step_index=0, error="Resource locked")
    step = planner.execute_step(plan, 0)
    assert step.completed is True


def test_feat_plan_003_plan_does_not_crash_on_failure():
    planner = TaskPlannerAdapter(ComputerControllerAdapter(), SafetyGuardAdapter())
    plan = planner.create_plan("Move latest PDF")
    # Recovery succeeds gracefully
    revised = planner.recover_plan(plan, failed_step_index=0, error="Disk read error")
    assert isinstance(revised, Plan)
    assert len(revised.steps) == 3
