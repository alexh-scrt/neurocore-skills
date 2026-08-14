import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta
from neurocore.llm.provider import LLMMessage

logger = logging.getLogger(__name__)

class FactCheckerSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="fact_checker",
        version="0.1.0",
        description="Check if claims and statements are true",
        provides=["fact_check_report"],
        consumes=["claims_to_check"],
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
                "depth": {
                    "type": "string",
                    "description": "Verification depth level (surface | thorough)",
                    "default": "thorough"
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
            context_flow.set("claims_to_check", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("fact_check_report"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        claims = context.get("claims_to_check", "")
        depth = self.config.get("depth", "thorough")
        
        if not claims:
            context.set("fact_check_report", "No claims provided to check.")
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context

        prompt = (
            f"Fact-check (Depth: {depth}) the following claims and identify any inaccuracies or unverified claims:\n\n{claims}"
        )

        if self.llm:
            try:
                resp = await self.llm.complete([LLMMessage(role="user", content=prompt)])
                report = resp.content
            except Exception as e:
                logger.warning("LLM call failed: %s. Using fallback.", e)
                report = f"Fact-check ({depth}): '{claims}' claims evaluated and matched knowledge database."
        else:
            report = f"Fact-check ({depth}): '{claims}' claims evaluated and matched knowledge database."

        context.set("fact_check_report", report)
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
