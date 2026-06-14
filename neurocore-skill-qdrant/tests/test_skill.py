"""Tests for QdrantSkill (search mocked via the _search seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_qdrant import QdrantSkill


def test_skill_meta():
    meta = QdrantSkill.skill_meta
    assert meta.name == "qdrant"
    assert "qdrant_results" in meta.provides


def test_validate_config_requires_collection():
    skill = QdrantSkill()
    skill.init({})
    assert any("collection" in e for e in skill.validate_config())


async def test_process_sets_results(monkeypatch):
    skill = QdrantSkill()
    skill.init({"collection": "docs"})

    async def fake_search(vector):
        assert vector == [0.1, 0.2]
        return [{"id": 1, "score": 0.9, "payload": {"text": "hi"}}]

    monkeypatch.setattr(skill, "_search", fake_search)
    ctx = FlowContext()
    ctx.set("query_vector", [0.1, 0.2])
    out = await skill.process(ctx)
    assert out.get("qdrant_results")[0]["score"] == 0.9


async def test_empty_vector_returns_empty():
    skill = QdrantSkill()
    skill.init({"collection": "docs"})
    out = await skill.process(FlowContext())
    assert out.get("qdrant_results") == []
