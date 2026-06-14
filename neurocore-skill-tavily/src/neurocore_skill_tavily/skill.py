"""TavilySkill — smart web search via the Tavily API.

Reads ``tavily_query`` from context, writes results to ``tavily_results``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)


class TavilySkill(AsyncSkill):
    """Async web search using the Tavily API."""

    skill_meta = SkillMeta(
        name="tavily",
        version="0.1.0",
        description="Smart web search via the Tavily API",
        author="NeuroCore Contributors",
        requires=["tavily-python>=0.5"],
        provides=["tavily_results"],
        consumes=["tavily_query"],
        tags=["search", "web", "research"],
        max_retries=3,
        retry_delay_base=2.0,
        retry_delay_max=30.0,
        config_schema={
            "properties": {
                "api_key": {"type": "string", "description": "Tavily API key."},
                "max_results": {"type": "integer"},
                "search_depth": {"type": "string", "enum": ["basic", "advanced"]},
            }
        },
    )

    def _resolve_api_key(self) -> str:
        return self.config.get("api_key", "") or os.environ.get("TAVILY_API_KEY", "")

    async def _search(self, query: str) -> list[dict[str, Any]]:
        """Call Tavily (blocking SDK run in a thread) and return result items."""
        from tavily import TavilyClient  # type: ignore[import-untyped]

        client = TavilyClient(api_key=self._resolve_api_key())
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": int(self.config.get("max_results", 5)),
            "search_depth": str(self.config.get("search_depth", "basic")),
        }
        response = await asyncio.to_thread(client.search, **kwargs)
        return list(response.get("results", []))

    async def process(self, context: FlowContext) -> FlowContext:
        query = str(context.get("tavily_query", ""))
        if not query:
            logger.warning("TavilySkill: 'tavily_query' is empty.")
            context.set("tavily_results", [])
            return context
        try:
            context.set("tavily_results", await self._search(query))
        except Exception as exc:  # noqa: BLE001
            logger.error("TavilySkill search failed: %s", exc, exc_info=True)
            context.set("tavily_results", [])
        return context
