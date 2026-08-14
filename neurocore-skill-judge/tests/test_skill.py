"""Tests for JudgeSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_judge import JudgeSkill


def test_skill_meta():
    assert JudgeSkill.skill_meta.name == "judge"
    assert "judge_evaluation" in JudgeSkill.skill_meta.provides
