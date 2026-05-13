"""
Phase 4 — Scene Agent
Breaks the script into visual scenes with timestamps, narration, and B-roll queries.
"""
import json
import re
from backend.agents.base_agent import BaseAgent


class SceneAgent(BaseAgent):
    PHASE_NUM = 3
    PHASE_NAME = "Scene Generation"

    async def run(self, pipeline_json: dict) -> dict:
        chunks = pipeline_json.get("chunks", [])
        if not chunks:
            script_text = pipeline_json.get("script", "")
            chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text) if s.strip()]
        
        topic = pipeline_json.get("selected_topic", "")
        video_style = pipeline_json.get("video_style", "realistic")
        
        # Check if we have feedback from a retry
        retry_context = pipeline_json.get("retry_feedback", {}).get(self.PHASE_NUM, "")
        retry_prompt = f"\nCRITICAL FIX REQUIRED FROM PREVIOUS RUN: {retry_context}\n" if retry_context else ""

        prompt = f"""
You are a YouTube Video Director AI agent specialized in scene planning.
{retry_prompt}
Video Topic: {topic}
Video Style: {video_style}
Script Chunks (one scene per chunk):
{json.dumps(chunks, indent=2)}

Break this script into a sequence of visual scenes.

RULES:
- 1 sentence (chunk) = 1 scene
- duration = 2–4 seconds per scene
- STYLE ADAPTATION:
    - If style is 'realistic': Generate 'keywords' that are concrete and searchable for stock footage (e.g., 'aerial view of mountains', 'busy city street at night', 'man typing on computer'). Avoid abstract concepts.
    - If style is 'cartoon': Generate 'keywords' and 'intent' that describe vibrant, animated, and whimsical 3D/2D cartoon visuals.

Return ONLY a valid JSON object matching this exact schema:
[
  {{
    "scene_id": 1,
    "text": "string — exact chunk text",
    "keywords": ["string — search keywords"],
    "intent": "string — visual intent",
    "duration": 3
  }}
]

Return ONLY valid JSON, no markdown fences.
"""
        try:
            scenes = await self.call_llm(prompt)
            if not isinstance(scenes, list):
                # If it returned a dict with "scenes" key
                if isinstance(scenes, dict) and "scenes" in scenes:
                    scenes = scenes["scenes"]
                else:
                    scenes = []
        except Exception:
            scenes = []

        normalized = []
        for idx, chunk in enumerate(chunks):
            scene = scenes[idx] if idx < len(scenes) and isinstance(scenes[idx], dict) else {}
            try:
                duration = int(scene.get("duration", 3))
            except:
                duration = 3
            
            normalized.append({
                "scene_id": idx + 1,
                "text": chunk,
                "keywords": scene.get("keywords", [topic]),
                "intent": scene.get("intent", f"Visualize: {chunk}"),
                "duration": max(2, min(6, duration)),
                # Adding visual_description for MediaAgent compatibility
                "visual_description": scene.get("intent", chunk)
            })

        return {
            "scenes": normalized,
            "scene_count": len(normalized),
            "target_scene_count": len(normalized)
        }
