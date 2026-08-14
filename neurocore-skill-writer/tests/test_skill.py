"""Tests for WriterSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_writer import WriterSkill


def test_skill_meta():
    assert WriterSkill.skill_meta.name == "writer"
    assert "written_content" in WriterSkill.skill_meta.provides
