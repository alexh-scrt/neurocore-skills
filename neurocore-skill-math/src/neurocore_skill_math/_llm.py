"""Base for LLM-backed math skills (problem prep, planning, formalization)."""
from __future__ import annotations

import json
import re
from typing import Any

from neurocore_skill_math._base import MathSkill

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Best-effort: parse the first JSON object in ``text``; else wrap as {'raw': ...}."""
    match = _JSON_RE.search(text or "")
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return {"raw": (text or "").strip()}


class LlmMathSkill(MathSkill):
    """MathSkill whose backend is the injected LLM provider (`requires_llm=True`)."""

    tool_name = "llm"

    def is_available(self) -> bool:
        return getattr(self, "llm", None) is not None

    async def _ask(self, user: str, system: str | None = None) -> str:
        from neurocore.llm.provider import LLMMessage

        response = await self.llm.complete(
            [LLMMessage(role="user", content=user)], system=system
        )
        return response.content

    async def _ask_json(self, user: str, system: str | None = None) -> dict[str, Any]:
        return extract_json(await self._ask(user, system))

    @staticmethod
    def _text(payload: Any, *keys: str) -> str:
        if isinstance(payload, str):
            return payload
        if hasattr(payload, "get"):
            for k in (*keys, "problem", "statement", "normalized", "raw"):
                v = payload.get(k)
                if isinstance(v, str) and v.strip():
                    return v
        return str(payload or "")
