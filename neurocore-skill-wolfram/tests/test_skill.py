"""Tests for WolframSkill (HTTP mocked via the _query seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_wolfram import WolframSkill


def test_skill_meta():
    assert WolframSkill.skill_meta.name == "wolfram"
    assert "wolfram_result" in WolframSkill.skill_meta.provides


async def test_process_sets_answer(monkeypatch):
    skill = WolframSkill()
    skill.init({"app_id": "x"})

    async def fake_query(q):
        assert "distance" in q
        return "384,400 km"

    monkeypatch.setattr(skill, "_query", fake_query)
    ctx = FlowContext()
    ctx.set("wolfram_query", "distance to the moon")
    out = await skill.process(ctx)
    assert out.get("wolfram_result") == "384,400 km"


async def test_empty_query():
    skill = WolframSkill()
    skill.init({"app_id": "x"})
    out = await skill.process(FlowContext())
    assert out.get("wolfram_result") == ""


async def test_error_sets_error_sentinel(monkeypatch):
    skill = WolframSkill()
    skill.init({"app_id": "x"})

    async def boom(q):
        raise RuntimeError("501")

    monkeypatch.setattr(skill, "_query", boom)
    ctx = FlowContext()
    ctx.set("wolfram_query", "q")
    out = await skill.process(ctx)
    assert "error" in out.get("wolfram_result")
