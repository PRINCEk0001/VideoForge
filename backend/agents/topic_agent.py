"""
Phase 2 — Topic Agent
Selects the single best topic from the trend list for a monetizable video.
"""
import json
from backend.agents.base_agent import BaseAgent


class TopicAgent(BaseAgent):
    PHASE_NUM = 2
    PHASE_NAME = "Topic Selection"

    async def run(self, pipeline_json: dict) -> dict:
        topics = pipeline_json.get("topics", [])
        topics_json = json.dumps(topics, indent=2)

        prompt = f"""
You are a YouTube Content Strategy AI agent.

You have received the following trend analysis data:
{topics_json}

Your task: Select the SINGLE BEST topic for creating a monetizable YouTube video.

Return ONLY a valid JSON object matching this exact schema:
{{
  "selected_topic": "string — exact topic title",
  "angle": "string — the hook or approach angle",
  "target_audience": "string — specific demographic",
  "justification": "string — why this topic is the best choice"
}}

CRITERIA:
- High curiosity
- Easy visualization
- Monetization safe

Return ONLY valid JSON, no markdown fences.
"""
        result = await self.call_llm(prompt)
        return result
