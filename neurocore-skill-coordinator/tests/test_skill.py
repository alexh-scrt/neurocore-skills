"""Tests for CoordinatorSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_coordinator import CoordinatorSkill


def test_skill_meta():
    assert CoordinatorSkill.skill_meta.name == "coordinator"
    assert "coordinator_status" in CoordinatorSkill.skill_meta.provides
