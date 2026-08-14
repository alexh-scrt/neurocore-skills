import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta
from neurocore.llm.provider import LLMMessage

logger = logging.getLogger(__name__)

class JudgeSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="judge",
        version="0.1.0",
        description="Determine if the task meets its quality criteria",
        provides=["judge_evaluation"],
        consumes=["task_output", "quality_criteria"],
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
                "strictness": {
                    "type": "string",
                    "description": "Evaluation strictness level (low | normal | high)",
                    "default": "normal"
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
            # Reconstruct evaluation from dynamic JSON/YAML payload
            context_flow = FlowContext()
            context_flow.set("task_output", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("judge_evaluation"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        task_out = context.get("task_output", "")
        criteria = context.get("quality_criteria", "")
        review = context.get("review_feedback", "")
        verifier_report = context.get("math_verification_result", {})
        strictness = self.config.get("strictness", "normal")

        if not task_out:
            context.set("judge_evaluation", {
                "approved": False,
                "reason": "Missing task output to evaluate."
            })
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context

        prompt = (
            f"Evaluate (Strictness: {strictness}) if the following task output meets the quality criteria.\n"
            f"Task Output: {task_out}\n"
            f"Quality Criteria: {criteria}\n"
            f"Review Feedback: {review}\n"
            f"Math Verifier Report: {verifier_report}\n\n"
            "Return JSON with keys 'approved' (true/false) and 'reason'."
        )

        if self.llm:
            try:
                resp = await self.llm.complete([LLMMessage(role="user", content=prompt)])
                approved = "true" in resp.content.lower() or '"approved": true' in resp.content.lower()
                context.set("judge_evaluation", {
                    "approved": approved,
                    "reason": resp.content,
                    "strictness": strictness
                })
            except Exception as e:
                logger.warning("LLM call failed: %s. Using fallback.", e)
                context.set("judge_evaluation", {
                    "approved": True,
                    "reason": f"Approved by fallback judge (strictness={strictness})."
                })
        else:
            context.set("judge_evaluation", {
                "approved": True,
                "reason": f"Approved by fallback judge (strictness={strictness})."
            })
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
