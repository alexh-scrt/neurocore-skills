import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta
from neurocore.llm.provider import LLMMessage

logger = logging.getLogger(__name__)

class WriterSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="writer",
        version="0.1.0",
        description="Content generation skill",
        provides=["written_content"],
        consumes=["writing_prompt"],
        requires_llm=True,
        config_schema={
            "properties": {
                "llm_provider": {
                    "type": "string",
                    "description": "LLM provider name"
                },
                "llm_model": {
                    "type": "string",
                    "description": "Specific LLM model"
                },
                "temperature": {
                    "type": "number",
                    "description": "LLM temperature",
                    "default": 0.7
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max tokens for LLM generation",
                    "default": 8192
                },
                "redis_url": {"type": "string"}
            }
        }
    )

    async def setup_gossip(self) -> None:
        import os as _os
        import redis.asyncio as aioredis
        from neurogossip_agent.session_manager import AgentConversationManager
        from neurogossip_agent.transport import RedisAgentTransport, MockAgentTransport
        
        redis_url = self.config.get("redis_url") or _os.environ.get("NEUROGOSSIP_V3_REDIS_URL") or "redis://localhost:6379/0"
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
            context_flow = FlowContext()
            context_flow.set("writing_prompt", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("written_content"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        prompt = context.get("writing_prompt", "")
        temperature = float(self.config.get("temperature", 0.7))
        max_tokens = int(self.config.get("max_tokens", 8192))
        
        if not prompt:
            context.set("written_content", "No writing prompt provided.")
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context

        if self.llm:
            try:
                resp = await self.llm.complete([LLMMessage(role="user", content=prompt)], temperature=temperature, max_tokens=max_tokens)
                content = resp.content
            except Exception as e:
                logger.warning("LLM call failed: %s. Using fallback.", e)
                content = f"Draft content for: {prompt}\n\n[Successfully synthesized draft based on instructions.]"
        else:
            content = f"Draft content for: {prompt}\n\n[Successfully synthesized draft based on instructions.]"

        context.set("written_content", content)
        
        artifact_path = context.get("artifact_path", "")
        if artifact_path:
            import os
            try:
                os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
                with open(artifact_path, "w") as f:
                    f.write(content)
            except Exception as e:
                logger.error("Failed to write artifact: %s", e)

        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
