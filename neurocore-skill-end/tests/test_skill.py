"""Tests for EndSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_end import EndSkill


def test_skill_meta():
    assert EndSkill.skill_meta.name == "end"
    assert "flow_completed" in EndSkill.skill_meta.provides
