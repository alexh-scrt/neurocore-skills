"""BraveSkill — web search via the Brave Search API.

Reads ``brave_query`` from context, writes results to ``brave_results``.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSkill(AsyncSkill):
    """Async web search using the Brave Search API."""

    skill_meta = SkillMeta(
        name="brave",
        version="0.1.0",
        description="Web search via the Brave Search API",
        author="NeuroCore Contributors",
        requires=["httpx>=0.27"],
        provides=["brave_results"],
        consumes=["brave_query"],
        tags=["search", "web"],
        max_retries=2,
        retry_delay_base=1.0,
        config_schema={
            "properties": {
                "api_key": {"type": "string", "description": "Brave API key."},
                "count": {"type": "integer", "description": "Max results (default 5)."},
                "country": {"type": "string"},
            }
        },
    )

    def _resolve_api_key(self) -> str:
        return self.config.get("api_key", "") or os.environ.get("BRAVE_API_KEY", "")

    async def _search(self, query: str) -> list[dict[str, Any]]:
        """Call the Brave API and return a list of result dicts."""
        import httpx

        params: dict[str, Any] = {"q": query, "count": int(self.config.get("count", 5))}
        if self.config.get("country"):
            params["country"] = self.config["country"]
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._resolve_api_key(),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_ENDPOINT, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return list(data.get("web", {}).get("results", []))

    async def process(self, context: FlowContext) -> FlowContext:
        query = str(context.get("brave_query", ""))
        if not query:
            logger.warning("BraveSkill: 'brave_query' is empty.")
            context.set("brave_results", [])
            return context
        try:
            context.set("brave_results", await self._search(query))
        except Exception as exc:  # noqa: BLE001
            logger.error("BraveSkill search failed: %s", exc, exc_info=True)
            context.set("brave_results", [])
        return context
