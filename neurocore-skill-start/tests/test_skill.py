"""Tests for StartSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_start import StartSkill


def test_skill_meta():
    assert StartSkill.skill_meta.name == "start"
    assert "flow_started" in StartSkill.skill_meta.provides
