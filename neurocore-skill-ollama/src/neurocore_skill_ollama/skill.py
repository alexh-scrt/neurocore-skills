from __future__ import annotations

import asyncio
import logging
import os
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class OllamaSkill(AsyncSkill):
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
            "properties": {
                "base_url": {"type": "string"},
                "model": {"type": "string"},
                "ollama_llm": {"type": "string", "description": "Ollama LLM model name"},
                "system": {"type": "string"},
                "redis_url": {"type": "string"}
            }
        }
    )

    def validate_config(self) -> list[str]:
        errors = super().validate_config()
        if "model" not in self.config and "ollama_llm" not in self.config:
            errors.append("Missing required config key: 'model' or 'ollama_llm'")
        return errors

    def _model_name(self) -> str:
        return self.config.get("ollama_llm") or self.config.get("model") or "llama3"

    def _base_url(self) -> str:
        return (
            self.config.get("base_url")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")

    async def _generate(self, prompt: str) -> str:
        import httpx
        payload = {
            "model": self._model_name(),
            "prompt": prompt,
            "stream": False,
        }
        if self.config.get("system"):
            payload["system"] = self.config["system"]
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._base_url()}/api/generate", json=payload)
            resp.raise_for_status()
            return str(resp.json().get("response", ""))

    async def setup_gossip(self) -> None:
        import redis.asyncio as aioredis
        from neurogossip_agent.session_manager import AgentConversationManager
        from neurogossip_agent.transport import RedisAgentTransport, MockAgentTransport
        
        redis_url = self.config.get("redis_url") or os.environ.get("NEUROGOSSIP_V3_REDIS_URL") or "redis://localhost:6379/0"
        try:
            self.redis_client = aioredis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()
            self.transport = RedisAgentTransport(agent_id=self.name, redis_url=redis_url)
            self.manager = AgentConversationManager(self.redis_client, self.transport)
        except Exception:
            self.redis_client = None
            self.transport = MockAgentTransport()
            self.manager = AgentConversationManager(None, self.transport)
        
        self.manager.register_handler(self._handle_gossip_message)
        await self.transport.connect()
        await self.manager.start_listening()

    async def teardown_gossip(self) -> None:
        if hasattr(self, "manager") and self.manager:
            await self.manager.stop_listening()
        if hasattr(self, "transport") and self.transport:
            await self.transport.disconnect()
        if hasattr(self, "redis_client") and self.redis_client:
            await self.redis_client.aclose()

    async def _handle_gossip_message(self, context, message_id, reply_to, tags, sender_id, payload) -> None:
        if "request" in tags:
            prompt = str(payload)
            logger.info("Ollama received gossip request: %s", prompt)
            try:
                response = await self._generate(prompt)
                await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=response)
            except Exception as e:
                logger.error("Gossip generation failed: %s", e)
                await self.manager.send_response(request_id=message_id, sender_id=self.name, payload={"error": str(e)})

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        prompt = str(context.get("prompt", ""))
        if prompt:
            try:
                context.set("ollama_response", await self._generate(prompt))
            except Exception as exc:
                logger.error("OllamaSkill generation failed: %s", exc, exc_info=True)
                context.set("ollama_response", {"error": str(exc)})
        else:
            context.set("ollama_response", "")

        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
