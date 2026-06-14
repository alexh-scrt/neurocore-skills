"""Tests for BraveSkill (network call mocked via the _search seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_brave import BraveSkill


def test_skill_meta():
    meta = BraveSkill.skill_meta
    assert meta.name == "brave"
    assert "brave_results" in meta.provides
    assert "brave_query" in meta.consumes


async def test_process_sets_results(monkeypatch):
    skill = BraveSkill()
    skill.init({"api_key": "x"})

    async def fake_search(query):
        assert query == "neurocore"
        return [{"title": "NeuroCore", "url": "https://example.com"}]

    monkeypatch.setattr(skill, "_search", fake_search)
    ctx = FlowContext()
    ctx.set("brave_query", "neurocore")
    out = await skill.process(ctx)
    assert out.get("brave_results")[0]["title"] == "NeuroCore"


async def test_empty_query_returns_empty():
    skill = BraveSkill()
    skill.init({"api_key": "x"})
    out = await skill.process(FlowContext())
    assert out.get("brave_results") == []


async def test_error_degrades_to_empty(monkeypatch):
    skill = BraveSkill()
    skill.init({"api_key": "x"})

    async def boom(query):
        raise RuntimeError("429")

    monkeypatch.setattr(skill, "_search", boom)
    ctx = FlowContext()
    ctx.set("brave_query", "q")
    out = await skill.process(ctx)
    assert out.get("brave_results") == []
