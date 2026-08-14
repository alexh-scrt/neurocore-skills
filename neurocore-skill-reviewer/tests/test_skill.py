"""Tests for ReviewerSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_reviewer import ReviewerSkill


def test_skill_meta():
    assert ReviewerSkill.skill_meta.name == "reviewer"
    assert "review_feedback" in ReviewerSkill.skill_meta.provides
