import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class CoordinatorSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="coordinator",
        version="0.1.0",
        description="Coordinate high level task by passing requests to other skills",
        provides=["coordinator_status"],
        consumes=["coordinator_flow_yaml"],
        config_schema={
            "properties": {
                "persistence_root": {
                    "type": "string",
                    "description": "Root path to persist step schedules and results"
                },
                "enable_human_checkpoints": {
                    "type": "boolean",
                    "description": "Enable interactive human checkpoints on task steps",
                    "default": False
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
            context_flow.set("coordinator_flow_yaml", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("coordinator_status"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        
        # Reset judge evaluation when coordinator starts/resumes coordination
        if context.has("judge_evaluation"):
            context.delete("judge_evaluation")
            
        task_plan = context.get("task_plan")
        if task_plan is not None:
            cycle_count = context.get("cycle_count", 0) + 1
            context.set("cycle_count", cycle_count)
            logger.info("Coordinator processing execution cycle step: %s", cycle_count)
            
            if cycle_count >= 2:
                context.set("flow_completed", True)
                context.set("coordinator_status", "no-task")
            else:
                context.set("coordinator_status", "has-next-task")
        else:
            context.set("coordinator_status", "need-plan")
            
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
