"""
Phase 10 — SEO Agent
Generates fully optimized YouTube metadata: title, description, tags, chapters, thumbnail text.
"""
import json
from backend.agents.base_agent import BaseAgent


class SEOAgent(BaseAgent):
    PHASE_NUM = 10
    PHASE_NAME = "SEO Generation"

    async def run(self, pipeline_json: dict) -> dict:
        topic = pipeline_json.get("selected_topic", "")
        
        prompt = f"""
🏷️ SEO PROMPT
Generate metadata for a video about: {topic}

Return ONLY JSON:
{{
  "title": "string",
  "description": "string",
  "hashtags": ["string"]
}}
"""
        result = await self.call_llm(prompt)
        return {"seo": result}
