"""QdrantSkill — vector similarity search over a Qdrant collection.

Reads a query vector from ``query_vector`` (list[float]) and writes hits to
``qdrant_results``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)


class QdrantSkill(AsyncSkill):
    """Async vector search against Qdrant."""

    skill_meta = SkillMeta(
        name="qdrant",
        version="0.1.0",
        description="Vector similarity search over a Qdrant collection",
        author="NeuroCore Contributors",
        requires=["qdrant-client>=1.10"],
        provides=["qdrant_results"],
        consumes=["query_vector"],
        tags=["vector", "rag", "retrieval"],
        max_retries=2,
        config_schema={
            "required": ["collection"],
            "properties": {
                "url": {"type": "string", "description": "Qdrant URL."},
                "api_key": {"type": "string"},
                "collection": {"type": "string"},
                "top_k": {"type": "integer"},
            },
        },
    )

    def _build_client(self) -> Any:
        from qdrant_client import QdrantClient  # type: ignore[import-untyped]

        url = self.config.get("url") or os.environ.get(
            "QDRANT_URL", "http://localhost:6333"
        )
        api_key = self.config.get("api_key") or os.environ.get("QDRANT_API_KEY")
        return QdrantClient(url=url, api_key=api_key)

    async def _search(self, vector: list[float]) -> list[dict[str, Any]]:
        """Run a similarity query and return hit dicts."""
        client = self._build_client()
        collection = self.config["collection"]
        top_k = int(self.config.get("top_k", 5))

        def _run() -> list[dict[str, Any]]:
            hits = client.query_points(
                collection_name=collection, query=vector, limit=top_k
            ).points
            return [
                {"id": h.id, "score": h.score, "payload": h.payload} for h in hits
            ]

        return await asyncio.to_thread(_run)

    async def process(self, context: FlowContext) -> FlowContext:
        vector = context.get("query_vector")
        if not vector:
            logger.warning("QdrantSkill: 'query_vector' is empty.")
            context.set("qdrant_results", [])
            return context
        try:
            context.set("qdrant_results", await self._search(list(vector)))
        except Exception as exc:  # noqa: BLE001
            logger.error("QdrantSkill search failed: %s", exc, exc_info=True)
            context.set("qdrant_results", [])
        return context
