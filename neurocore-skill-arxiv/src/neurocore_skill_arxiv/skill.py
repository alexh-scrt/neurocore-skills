import asyncio
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from flowengine import FlowContext
from neurocore import AsyncSkill, SkillMeta

logger = logging.getLogger(__name__)

class ArxivSkill(AsyncSkill):
    skill_meta = SkillMeta(
        name="arxiv",
        version="0.1.0",
        description="Search arxiv.org for articles related to the topic of research",
        provides=["arxiv_results"],
        consumes=["arxiv_query"],
        config_schema={
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of arXiv search results to return",
                    "default": 3
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
            logger.info("Arxiv received gossip request: %s", payload)
            # Heuristic echo/mock or run query if string
            context_flow = FlowContext()
            context_flow.set("arxiv_query", str(payload))
            res_ctx = await self.process(context_flow)
            await self.manager.send_response(request_id=message_id, sender_id=self.name, payload=res_ctx.get("arxiv_results"))

    async def process(self, context: FlowContext) -> FlowContext:
        await self.setup_gossip()
        query = context.get("arxiv_query", "")
        max_results = int(self.config.get("max_results", 3))
        if not query:
            context.set("arxiv_results", [])
            await asyncio.sleep(0.05)
            await self.teardown_gossip()
            return context
        
        try:
            safe_query = urllib.parse.quote(query)
            url = f"http://export.arxiv.org/api/query?search_query=all:{safe_query}&max_results={max_results}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
            
            root = ET.fromstring(xml_data)
            results = []
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title_node = entry.find("{http://www.w3.org/2005/Atom}title")
                summary_node = entry.find("{http://www.w3.org/2005/Atom}summary")
                id_node = entry.find("{http://www.w3.org/2005/Atom}id")
                
                title = title_node.text.strip() if title_node is not None else "No Title"
                summary = summary_node.text.strip() if summary_node is not None else "No Summary"
                id_url = id_node.text.strip() if id_node is not None else ""
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": id_url
                })
            context.set("arxiv_results", results)
        except Exception as e:
            logger.error("Arxiv query failed: %s", e)
            context.set("arxiv_results", [{"error": str(e)}])
        
        await asyncio.sleep(0.05)
        await self.teardown_gossip()
        return context
