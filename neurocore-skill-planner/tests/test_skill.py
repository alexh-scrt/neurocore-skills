"""Tests for PlannerSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_planner import PlannerSkill


def test_skill_meta():
    assert PlannerSkill.skill_meta.name == "planner"
    assert "task_plan" in PlannerSkill.skill_meta.provides
