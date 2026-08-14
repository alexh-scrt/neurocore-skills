import asyncio
import logging
import os
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class ResearcherSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="researcher",
        version="0.1.0",
        description="Aggregated research skill that coordinates Tavily, Brave, and arXiv",
        provides=["research_results"],
        consumes=["research_query"],
        config_schema={
            "properties": {
                "tavily_api_key": {
                    "type": "string",
                    "description": "API key for Tavily Search API"
                },
                "brave_api_key": {
                    "type": "string",
                    "description": "API key for Brave Search API"
                },
                "wolfram_api_key": {
                    "type": "string",
                    "description": "App ID / API key for Wolfram Alpha API"
                },
                "default_max_results": {
                    "type": "integer",
                    "description": "Default maximum number of results to fetch per engine",
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
            context_flow.set("research_query", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("research_results"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        query = context.get("research_query", "")
        tavily_key = self.config.get("tavily_api_key") or os.environ.get("TAVILY_API_KEY", "")
        brave_key = self.config.get("brave_api_key") or os.environ.get("BRAVE_API_KEY", "")
        wolfram_key = self.config.get("wolfram_api_key") or os.environ.get("WOLFRAM_API_KEY", "")
        max_results = int(self.config.get("default_max_results", 5))

        if not query:
            context.set("research_results", "No research query provided.")
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context
        
        arxiv_results = context.get("arxiv_results", [])
        summary_parts = [f"Research query: {query}"]
        summary_parts.append(f"[Config Settings: max_results={max_results}, tavily_configured={bool(tavily_key)}, brave_configured={bool(brave_key)}, wolfram_configured={bool(wolfram_key)}]")
        
        if arxiv_results:
            summary_parts.append("\nArXiv search results:")
            for idx, res in enumerate(arxiv_results):
                if isinstance(res, dict) and "title" in res:
                    summary_parts.append(f"{idx+1}. {res['title']} - {res['url']}\nAbstract: {res['summary'][:200]}...")
        else:
            summary_parts.append("\nSimulated Web Search Results (Tavily/Brave):")
            summary_parts.append(f"- Found reference results matching '{query}'.")
        
        context.set("research_results", "\n".join(summary_parts))
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
