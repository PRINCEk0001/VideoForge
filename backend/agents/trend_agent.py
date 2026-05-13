"""
Phase 1 — Trend Agent
Identifies currently trending, monetizable YouTube topics.
"""
import json
import os

from backend.agents.base_agent import BaseAgent


class TrendAgent(BaseAgent):
    PHASE_NUM = 1
    PHASE_NAME = "Trend Analysis"

    def _load_configured_topics(self):
        """
        Optional trend source adapter:
        - TREND_SOURCE=static_json
        - TREND_TOPICS_JSON='[{"title":"...", "keywords":["..."], "audience":"...", "score":0.8, "reason":"..."}]'
        """
        trend_source = (os.getenv("TREND_SOURCE") or "").strip().lower()
        if trend_source != "static_json":
            return None

        raw = (os.getenv("TREND_TOPICS_JSON") or "").strip()
        if not raw:
            return None

        try:
            topics = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if not isinstance(topics, list) or not topics:
            return None

        normalized = []
        for item in topics[:3]:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "keywords": item.get("keywords", []) if isinstance(item.get("keywords", []), list) else [],
                    "audience": str(item.get("audience", "general")).strip() or "general",
                    "score": float(item.get("score", 0.7) or 0.7),
                    "reason": str(item.get("reason", "Configured trend source")).strip() or "Configured trend source",
                    "source": "configured_static_json",
                }
            )

        return normalized if normalized else None

    async def run(self, pipeline_json: dict) -> dict:
        configured_topics = self._load_configured_topics()
        if configured_topics:
            return {"topics": configured_topics, "trend_source": "configured_static_json"}

        hint = pipeline_json.get("topic_hint", "")
        hint_clause = f'Focus on the niche: "{hint}".' if hint else "Cover diverse niches."

        prompt = f"""
You are a YouTube Trend Analysis AI agent.
{hint_clause}

Your task: identify currently trending YouTube video topics that have strong monetization potential.

Return ONLY a valid JSON object matching this exact schema:
{{
  "topics": [
    {{
      "title": "string — clear video topic title",
      "keywords": ["string — keyword 1", "string — keyword 2"],
      "audience": "string — target audience",
      "score": 0.0,
      "reason": "string — why it's trending"
    }}
  ]
}}

Rules:
- Only high-engagement topics
- No unsafe or sensitive content
- Max 3 topics
- Return ONLY valid JSON, no markdown fences
"""
        result = await self.call_llm(prompt)
        result["trend_source"] = "llm_generated"
        return result
