"""
Phase 3 — Script Agent
Writes a full, platform-optimized video script with hook, body, and CTA.
"""
import json
from backend.agents.base_agent import BaseAgent


class ScriptAgent(BaseAgent):
    PHASE_NUM = 2
    PHASE_NAME = "Script Processing"

    async def run(self, pipeline_json: dict) -> dict:
        topic = pipeline_json.get("selected_topic", "")
        video_style = pipeline_json.get("video_style", "realistic")
        user_script = pipeline_json.get("user_script", "").strip()
        
        # Check if we have feedback from a retry
        retry_context = pipeline_json.get("retry_feedback", {}).get(self.PHASE_NUM, "")
        retry_prompt = f"\nCRITICAL FIX REQUIRED FROM PREVIOUS RUN: {retry_context}\n" if retry_context else ""

        if user_script:
            prompt = f"""
You are an expert script editor.
The user has provided their own script below. Your job is to format it for the video pipeline.
{retry_prompt}
USER SCRIPT:
\"\"\"{user_script}\"\"\"

TASK:
1. Split the script into short, speech-optimized sentences (chunks).
2. Keep the meaning and tone exactly as the user wrote it, but ensure every sentence is conversational.
3. If the user script is very long, ensure it remains coherent.

Return ONLY a valid JSON object matching this exact schema:
{{
  "script": "string — the full script text",
  "chunks": [
    "string — sentence 1",
    "string — sentence 2"
  ]
}}
"""
        else:
            audience = pipeline_json.get("target_audience", "general audience")
            angle = pipeline_json.get("angle", "curiosity")
            target_scene_count = pipeline_json.get("target_scene_count", 5)
            target_duration_minutes = pipeline_json.get("target_duration_minutes", 0)
            
            duration_instruction = f"The video should be approximately {target_duration_minutes} minutes long." if target_duration_minutes > 0 else ""

            prompt = f"""
You are an elite, award-winning YouTube Script Writer.
{retry_prompt}
Video Topic: {topic}
Video Style: {video_style}
Target Audience: {audience}
Hook Angle: {angle}
Target Scene Count: {target_scene_count}
{duration_instruction}

Write a complete, highly engaging YouTube video script optimized for maximum watch time and monetization.

RULES:
- STYLE ADAPTATION: If style is 'cartoon', use a more playful, storytelling, whimsical, or animated tone. If 'realistic', keep it professional and documentary-style.
- STRONG HOOK: The first 3 seconds must immediately grab attention.
- SHORT SENTENCES: No long, complex sentences. One thought per sentence.
- CONVERSATIONAL TONE: Must sound like a real person talking.
- EXACTLY {target_scene_count} SENTENCES: The total number of sentences (chunks) MUST be exactly {target_scene_count}.
- NO REPETITION: Do not repeat facts, words, or concepts across different sentences. Every sentence must add new value.
- NARRATIVE VARIETY: Ensure a clear progression from Hook -> Value -> Conclusion without looping ideas.

Return ONLY a valid JSON object matching this exact schema:
{{
  "script": "string — the full script text",
  "chunks": [
    "string — sentence 1",
    "string — sentence 2"
  ]
}}
"""
        result = await self.call_llm(prompt)
        # Compatibility with existing pipeline structure
        if "script" in result:
             result["short_script"] = {"body": result["script"]}
        return result
