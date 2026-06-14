"""WolframSkill — computational answers via the Wolfram|Alpha Short Answers API.

Reads ``wolfram_query`` from context, writes a string to ``wolfram_result``.
"""
from __future__ import annotations

import logging
import os

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.wolframalpha.com/v1/result"


class WolframSkill(AsyncSkill):
    """Async computational-knowledge lookups via Wolfram|Alpha."""

    skill_meta = SkillMeta(
        name="wolfram",
        version="0.1.0",
        description="Computational answers via Wolfram|Alpha",
        author="NeuroCore Contributors",
        requires=["httpx>=0.27"],
        provides=["wolfram_result"],
        consumes=["wolfram_query"],
        tags=["math", "compute", "knowledge"],
        max_retries=2,
        config_schema={
            "properties": {
                "app_id": {"type": "string", "description": "Wolfram|Alpha AppID."},
                "units": {"type": "string", "enum": ["metric", "imperial"]},
            }
        },
    )

    def _resolve_app_id(self) -> str:
        return self.config.get("app_id", "") or os.environ.get("WOLFRAM_APP_ID", "")

    async def _query(self, question: str) -> str:
        """Call the Short Answers API and return the plain-text answer."""
        import httpx

        params = {"appid": self._resolve_app_id(), "i": question}
        if self.config.get("units"):
            params["units"] = self.config["units"]
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_ENDPOINT, params=params)
            resp.raise_for_status()
            return resp.text

    async def process(self, context: FlowContext) -> FlowContext:
        question = str(context.get("wolfram_query", ""))
        if not question:
            logger.warning("WolframSkill: 'wolfram_query' is empty.")
            context.set("wolfram_result", "")
            return context
        try:
            context.set("wolfram_result", await self._query(question))
        except Exception as exc:  # noqa: BLE001
            logger.error("WolframSkill query failed: %s", exc, exc_info=True)
            context.set("wolfram_result", {"error": str(exc)})
        return context
