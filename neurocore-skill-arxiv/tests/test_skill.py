"""Tests for ArxivSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_arxiv import ArxivSkill


def test_skill_meta():
    assert ArxivSkill.skill_meta.name == "arxiv"
    assert "arxiv_results" in ArxivSkill.skill_meta.provides
