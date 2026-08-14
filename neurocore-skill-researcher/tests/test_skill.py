"""Tests for ResearcherSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_researcher import ResearcherSkill


def test_skill_meta():
    assert ResearcherSkill.skill_meta.name == "researcher"
    assert "research_results" in ResearcherSkill.skill_meta.provides
