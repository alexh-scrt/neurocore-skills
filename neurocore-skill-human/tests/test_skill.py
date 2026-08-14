"""Tests for HumanSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_human import HumanSkill


def test_skill_meta():
    assert HumanSkill.skill_meta.name == "human"
    assert "human_decision" in HumanSkill.skill_meta.provides
