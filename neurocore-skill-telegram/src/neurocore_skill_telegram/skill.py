"""TelegramSkill — send a message via the Telegram Bot API.

Reads ``telegram_text`` (and optional ``telegram_chat_id``) from context and
writes the API response to ``telegram_result``.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)


class TelegramSkill(AsyncSkill):
    """Async Telegram message sender."""

    skill_meta = SkillMeta(
        name="telegram",
        version="0.1.0",
        description="Send messages via the Telegram Bot API",
        author="NeuroCore Contributors",
        requires=["httpx>=0.27"],
        provides=["telegram_result"],
        consumes=["telegram_text", "telegram_chat_id"],
        tags=["messaging", "notify", "telegram"],
        max_retries=2,
        config_schema={
            "properties": {
                "bot_token": {"type": "string"},
                "chat_id": {"type": "string"},
                "parse_mode": {"type": "string"},
            }
        },
    )

    def _resolve_token(self) -> str:
        return self.config.get("bot_token", "") or os.environ.get(
            "TELEGRAM_BOT_TOKEN", ""
        )

    async def _send(self, chat_id: str, text: str) -> dict[str, Any]:
        """Call the Bot API sendMessage and return the JSON response."""
        import httpx

        token = self._resolve_token()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if self.config.get("parse_mode"):
            payload["parse_mode"] = self.config["parse_mode"]
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return dict(resp.json())

    async def process(self, context: FlowContext) -> FlowContext:
        text = str(context.get("telegram_text", ""))
        chat_id = str(context.get("telegram_chat_id") or self.config.get("chat_id", ""))
        if not text or not chat_id:
            logger.warning("TelegramSkill: missing 'telegram_text' or chat id.")
            context.set("telegram_result", {"ok": False, "error": "missing text/chat_id"})
            return context
        try:
            context.set("telegram_result", await self._send(chat_id, text))
        except Exception as exc:  # noqa: BLE001
            logger.error("TelegramSkill send failed: %s", exc, exc_info=True)
            context.set("telegram_result", {"ok": False, "error": str(exc)})
        return context
