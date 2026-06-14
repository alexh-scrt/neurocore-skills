"""Tests for OllamaSkill (HTTP mocked via the _generate seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_ollama import OllamaSkill


def test_skill_meta():
    assert OllamaSkill.skill_meta.name == "ollama"
    assert "ollama_response" in OllamaSkill.skill_meta.provides


def test_validate_requires_model():
    skill = OllamaSkill()
    skill.init({})
    assert any("model" in e for e in skill.validate_config())


async def test_process_generates(monkeypatch):
    skill = OllamaSkill()
    skill.init({"model": "llama3.2"})

    async def fake_generate(prompt):
        assert prompt == "hi"
        return "hello there"

    monkeypatch.setattr(skill, "_generate", fake_generate)
    ctx = FlowContext()
    ctx.set("prompt", "hi")
    out = await skill.process(ctx)
    assert out.get("ollama_response") == "hello there"


async def test_empty_prompt():
    skill = OllamaSkill()
    skill.init({"model": "llama3.2"})
    out = await skill.process(FlowContext())
    assert out.get("ollama_response") == ""


async def test_error_sentinel(monkeypatch):
    skill = OllamaSkill()
    skill.init({"model": "llama3.2"})

    async def boom(prompt):
        raise RuntimeError("no server")

    monkeypatch.setattr(skill, "_generate", boom)
    ctx = FlowContext()
    ctx.set("prompt", "x")
    out = await skill.process(ctx)
    assert "error" in out.get("ollama_response")
