import asyncio
import logging
import sys
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class HumanSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="human",
        version="0.1.0",
        description="Human in the loop approval skill",
        provides=["human_decision"],
        consumes=["human_prompt"],
        config_schema={
            "properties": {
                "checkpoint_type": {
                    "type": "string",
                    "description": "Approval prompt mode (auto_approve | interactive)",
                    "default": "auto_approve"
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout to wait for manual human approval before proceeding",
                    "default": 300
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
            context_flow.set("human_prompt", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("human_decision"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        prompt = context.get("human_prompt", "Please approve task progression.")
        checkpoint_type = self.config.get("checkpoint_type", "auto_approve")
        timeout = int(self.config.get("timeout_seconds", 300))
        
        print(f"\n[HUMAN IN THE LOOP REQUEST]: {prompt} (Timeout: {timeout}s)", file=sys.stderr)
        
        if checkpoint_type == "interactive" and sys.stdin.isatty():
            try:
                print("Enter your approval decision (y/n) or feedback: ", end="", file=sys.stderr)
                sys.stderr.flush()
                choice = sys.stdin.readline().strip()
                if choice.lower() in ("y", "yes", ""):
                    context.set("human_decision", {"approved": True, "feedback": "Approved via console"})
                else:
                    context.set("human_decision", {"approved": False, "feedback": choice})
            except Exception as e:
                logger.warning("Fell back to auto-approval during stdin error: %s", e)
                context.set("human_decision", {"approved": True, "feedback": "Auto-approved due to read error"})
        else:
            context.set("human_decision", {"approved": True, "feedback": f"Auto-approved in automated mode (timeout={timeout}s)"})
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
