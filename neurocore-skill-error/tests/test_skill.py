"""Tests for ErrorSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_error import ErrorSkill


def test_skill_meta():
    assert ErrorSkill.skill_meta.name == "error"
    assert "error_report" in ErrorSkill.skill_meta.provides
