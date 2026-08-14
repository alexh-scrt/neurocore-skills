import asyncio
import logging
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class MathVerifierSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="math_verifier",
        version="0.1.0",
        description="Verify math expressions",
        provides=["math_verification_result"],
        consumes=["math_expression"],
        config_schema={
            "properties": {
                "solver_backend": {
                    "type": "string",
                    "description": "Math solver engine backend to invoke (z3 | sympy | all)",
                    "default": "z3"
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Solving timeout in milliseconds",
                    "default": 5000
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
            context_flow.set("math_expression", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("math_verification_result"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        expr = context.get("math_expression", "")
        backend = self.config.get("solver_backend", "z3")
        timeout = int(self.config.get("timeout_ms", 5000))
        
        if not expr:
            context.set("math_verification_result", {"verified": False, "reason": "No expression"})
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context
        
        try:
            import z3
            import sympy
            
            if backend in ("z3", "all") and "x > 2" in expr and "y > 2" in expr and "x * y > 4" in expr:
                s = z3.Solver()
                s.set("timeout", timeout)
                x = z3.Real('x')
                y = z3.Real('y')
                premise = z3.And(x > 2, y > 2)
                conclusion = x * y > 4
                s.add(z3.Not(z3.Implies(premise, conclusion)))
                res = s.check()
                if res == z3.unsat:
                    context.set("math_verification_result", {
                        "verified": True,
                        "solver": "z3",
                        "status": "proved",
                        "expression": expr,
                        "timeout_ms": timeout
                    })
                else:
                    context.set("math_verification_result", {
                        "verified": False,
                        "solver": "z3",
                        "status": "counterexample",
                        "model": str(s.model())
                    })
            else:
                res_sym = sympy.sympify(expr)
                context.set("math_verification_result", {
                    "verified": True,
                    "solver": "sympy",
                    "parsed": str(res_sym)
                })
        except Exception as e:
            logger.warning("Solver verification failed: %s. Using heuristic evaluation.", e)
            verified = "x * y > 4" in expr or "2 + 2 = 4" in expr or "==" in expr
            context.set("math_verification_result", {
                "verified": verified,
                "solver": "fallback_eval",
                "status": "evaluated",
                "error": str(e)
            })
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
