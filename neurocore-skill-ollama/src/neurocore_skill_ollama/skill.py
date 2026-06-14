"""OllamaSkill — text generation via a local Ollama server.

Reads ``prompt`` from context, writes the generated text to ``ollama_response``.

Tip: for chat-style LLM access inside skills that set ``requires_llm=True``, use
NeuroCore's built-in ``ollama`` provider instead. This skill is a direct,
provider-free call to Ollama's ``/api/generate`` endpoint.
"""
from __future__ import annotations

import logging
import os

from flowengine import FlowContext

from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)


class OllamaSkill(AsyncSkill):
    """Async text generation against a local Ollama server."""

    skill_meta = SkillMeta(
        name="ollama",
        version="0.1.0",
        description="Text generation via a local Ollama server",
        author="NeuroCore Contributors",
        requires=["httpx>=0.27"],
        provides=["ollama_response"],
        consumes=["prompt"],
        tags=["llm", "local", "generation"],
        max_retries=2,
        config_schema={
            "required": ["model"],
            "properties": {
                "base_url": {"type": "string"},
                "model": {"type": "string"},
                "system": {"type": "string"},
            },
        },
    )

    def _base_url(self) -> str:
        return (
            self.config.get("base_url")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")

    async def _generate(self, prompt: str) -> str:
        """Call Ollama /api/generate and return the response text."""
        import httpx

        payload = {
            "model": self.config["model"],
            "prompt": prompt,
            "stream": False,
        }
        if self.config.get("system"):
            payload["system"] = self.config["system"]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._base_url()}/api/generate", json=payload)
            resp.raise_for_status()
            return str(resp.json().get("response", ""))

    async def process(self, context: FlowContext) -> FlowContext:
        prompt = str(context.get("prompt", ""))
        if not prompt:
            logger.warning("OllamaSkill: 'prompt' is empty.")
            context.set("ollama_response", "")
            return context
        try:
            context.set("ollama_response", await self._generate(prompt))
        except Exception as exc:  # noqa: BLE001
            logger.error("OllamaSkill generation failed: %s", exc, exc_info=True)
            context.set("ollama_response", {"error": str(exc)})
        return context
