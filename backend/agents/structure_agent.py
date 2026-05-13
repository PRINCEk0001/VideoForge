"""
Phase 8 — Structure Agent
Builds the final video timeline JSON mapping scenes to timestamps with transitions.
"""
import json
from backend.agents.base_agent import BaseAgent


class StructureAgent(BaseAgent):
    PHASE_NUM = 7
    PHASE_NAME = "Video Structuring"

    async def run(self, pipeline_json: dict) -> dict:
        scenes = pipeline_json.get("scenes", [])
        topic = pipeline_json.get("selected_topic", "")

        # Summarize scenes for the prompt
        scene_summary = [
            {
                "id": idx + 1,
                "duration": s.get("duration", 3),
                "narration_preview": s.get("text", "")[:80],
                "media_url": s.get("media", {}).get("url", ""),
            }
            for idx, s in enumerate(scenes)
        ]

        prompt = f"""
You are a Video Editor AI agent building the final timeline structure for a YouTube video.

Topic: {topic}
Scenes:
{json.dumps(scene_summary, indent=2)}

Build a complete, production-ready video timeline.

Return ONLY a valid JSON object matching this exact schema:
{{
  "timeline": [
    {{
      "scene_id": 1,
      "duration": 3,
      "text": "string — narration text",
      "visual": "string — visual description or media URL",
      "subtitle": "string — subtitle to display"
    }}
  ]
}}

Return ONLY valid JSON, no markdown fences.
"""
        try:
            result = await self.call_llm(prompt)
            timeline = result.get("timeline", [])
            if not timeline or len(timeline) < len(scenes):
                # If LLM failed or missed scenes, merge its metadata back into the original list
                timeline = []
                for idx, s in enumerate(scenes):
                    timeline.append({
                        "scene_id": s.get("scene_id", idx + 1),
                        "duration": s.get("duration", 3),
                        "text": s.get("text", ""),
                        "visual": s.get("media", {}).get("url", ""),
                        "subtitle": s.get("text", "")
                    })
        except Exception:
            # Complete fallback: just use the scenes we have
            timeline = []
            for idx, s in enumerate(scenes):
                timeline.append({
                    "scene_id": s.get("scene_id", idx + 1),
                    "duration": s.get("duration", 3),
                    "text": s.get("text", ""),
                    "visual": s.get("media", {}).get("url", ""),
                    "subtitle": s.get("text", "")
                })

        return {"timeline": timeline}
