import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class ErrorSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="error",
        version="0.1.0",
        description="Process an error",
        provides=["error_report"],
        consumes=["error_context"],
        config_schema={
            "properties": {
                "notify_on_failure": {
                    "type": "boolean",
                    "description": "Post notifications to alerting integrations on failure",
                    "default": False
                },
                "alert_channel": {
                    "type": "string",
                    "description": "Specific notification alert webhook or room"
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
            context_flow.set("error_context", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("error_report"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        error_context = context.get("error_context", "Unknown error")
        notify = bool(self.config.get("notify_on_failure", False))
        channel = self.config.get("alert_channel", "default")
        
        logger.error("NeuroCore Flow Error Triggered: %s. Alerting channel '%s' (notify=%s)", error_context, channel, notify)
        context.set("error_report", {
            "status": "failed",
            "error_msg": str(error_context),
            "alerted": notify
        })
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
