"""Tests for FactCheckerSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_fact_checker import FactCheckerSkill


def test_skill_meta():
    assert FactCheckerSkill.skill_meta.name == "fact_checker"
    assert "fact_check_report" in FactCheckerSkill.skill_meta.provides
