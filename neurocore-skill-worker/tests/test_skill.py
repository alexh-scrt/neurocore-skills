"""Tests for WorkerSkill."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_worker import WorkerSkill


def test_skill_meta():
    assert WorkerSkill.skill_meta.name == "worker"
    assert "worker_output" in WorkerSkill.skill_meta.provides
