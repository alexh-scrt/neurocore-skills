"""Tests for TavilySkill (SDK call mocked via the _search seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_tavily import TavilySkill


def test_skill_meta():
    meta = TavilySkill.skill_meta
    assert meta.name == "tavily"
    assert "tavily_results" in meta.provides
    assert "tavily_query" in meta.consumes


async def test_process_sets_results(monkeypatch):
    skill = TavilySkill()
    skill.init({"api_key": "x"})

    async def fake_search(query):
        return [{"title": "r", "url": "u", "content": "c"}]

    monkeypatch.setattr(skill, "_search", fake_search)
    ctx = FlowContext()
    ctx.set("tavily_query", "q")
    out = await skill.process(ctx)
    assert out.get("tavily_results")[0]["url"] == "u"


async def test_empty_query_returns_empty():
    skill = TavilySkill()
    skill.init({"api_key": "x"})
    out = await skill.process(FlowContext())
    assert out.get("tavily_results") == []


async def test_error_degrades_to_empty(monkeypatch):
    skill = TavilySkill()
    skill.init({"api_key": "x"})

    async def boom(query):
        raise RuntimeError("bad key")

    monkeypatch.setattr(skill, "_search", boom)
    ctx = FlowContext()
    ctx.set("tavily_query", "q")
    out = await skill.process(ctx)
    assert out.get("tavily_results") == []
