"""Tests for TelegramSkill (HTTP mocked via the _send seam)."""
from __future__ import annotations

from flowengine import FlowContext
from neurocore_skill_telegram import TelegramSkill


def test_skill_meta():
    assert TelegramSkill.skill_meta.name == "telegram"
    assert "telegram_result" in TelegramSkill.skill_meta.provides


async def test_process_sends(monkeypatch):
    skill = TelegramSkill()
    skill.init({"bot_token": "t", "chat_id": "123"})

    async def fake_send(chat_id, text):
        assert chat_id == "123"
        assert text == "hello"
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(skill, "_send", fake_send)
    ctx = FlowContext()
    ctx.set("telegram_text", "hello")
    out = await skill.process(ctx)
    assert out.get("telegram_result").get("ok") is True


async def test_runtime_chat_id_overrides(monkeypatch):
    skill = TelegramSkill()
    skill.init({"bot_token": "t", "chat_id": "config-chat"})

    seen = {}

    async def fake_send(chat_id, text):
        seen["chat_id"] = chat_id
        return {"ok": True}

    monkeypatch.setattr(skill, "_send", fake_send)
    ctx = FlowContext()
    ctx.set("telegram_text", "hi")
    ctx.set("telegram_chat_id", "runtime-chat")
    await skill.process(ctx)
    assert seen["chat_id"] == "runtime-chat"


async def test_missing_text_or_chat():
    skill = TelegramSkill()
    skill.init({"bot_token": "t"})
    out = await skill.process(FlowContext())
    assert out.get("telegram_result").get("ok") is False


async def test_error_sentinel(monkeypatch):
    skill = TelegramSkill()
    skill.init({"bot_token": "t", "chat_id": "1"})

    async def boom(chat_id, text):
        raise RuntimeError("401")

    monkeypatch.setattr(skill, "_send", boom)
    ctx = FlowContext()
    ctx.set("telegram_text", "hi")
    out = await skill.process(ctx)
    result = out.get("telegram_result")
    assert result.get("ok") is False
    assert "401" in result.get("error")
