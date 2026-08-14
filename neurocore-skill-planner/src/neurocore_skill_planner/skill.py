import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta
from neurocore.llm.provider import LLMMessage

logger = logging.getLogger(__name__)

class PlannerSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="planner",
        version="0.1.0",
        description="Task execution planning and coordination skill for NeuroCore",
        provides=["task_plan"],
        consumes=["task_description"],
        requires_llm=True,
        config_schema={
            "properties": {
                "llm_provider": {
                    "type": "string",
                    "description": "LLM provider name (e.g. openai, anthropic, gemini, ollama, mock)",
                    "default": "mock"
                },
                "llm_model": {
                    "type": "string",
                    "description": "Specific LLM model to query"
                },
                "temperature": {
                    "type": "number",
                    "description": "LLM temperature tuning parameter",
                    "default": 0.7
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max tokens for LLM generation",
                    "default": 4096
                },
                "max_refinement_cycles": {
                    "type": "integer",
                    "description": "Cap on refinement planning loops",
                    "default": 5
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
            context_flow.set("task_description", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("task_plan"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        task_desc = context.get("task_description", "")
        max_cycles = int(self.config.get("max_refinement_cycles", 5))
        temperature = float(self.config.get("temperature", 0.7))
        
        if not task_desc:
            context.set("task_plan", "No task description provided.")
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context

        prompt = (
            f"Draft a detailed task execution plan (as a YAML list of steps) for: {task_desc}.\n"
            f"Keep it to structured steps with step_id, description, and assigned_worker. Max refinement cycles: {max_cycles}."
        )

        if self.llm:
            try:
                resp = await self.llm.complete([LLMMessage(role="user", content=prompt)], temperature=temperature)
                plan_text = resp.content
            except Exception as e:
                logger.warning("LLM call failed: %s. Using fallback.", e)
                plan_text = self._fallback_plan(task_desc)
        else:
            plan_text = self._fallback_plan(task_desc)

        context.set("task_plan", plan_text)
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context

    def _fallback_plan(self, task_desc: str) -> str:
        return f"""plan_id: "plan_auto_generated"
goal: {task_desc}
execution_steps:
  - step_id: "step_1"
    description: "Research domain context for: {task_desc}"
    assigned_worker: "worker"
  - step_id: "step_2"
    description: "Verify expression or generate final output"
    assigned_worker: "worker"
"""
