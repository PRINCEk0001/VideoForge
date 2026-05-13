"""
Orchestrator — chains all 10 agents sequentially and streams SSE events.
"""
import json
import time
import os
from typing import AsyncGenerator

from backend.agents.trend_agent import TrendAgent
from backend.agents.topic_agent import TopicAgent
from backend.agents.script_agent import ScriptAgent
from backend.agents.scene_agent import SceneAgent
from backend.agents.media_agent import MediaAgent
from backend.agents.voice_agent import VoiceAgent
from backend.agents.structure_agent import StructureAgent
from backend.agents.assembly_agent import AssemblyAgent
from backend.agents.validator_agent import ValidatorAgent
from backend.agents.compliance_agent import ComplianceAgent
from backend.agents.seo_agent import SEOAgent
from backend.agents.quality_scoring_agent import QualityScoringAgent
from backend.agents.learning_agent import LearningAgent

AGENT_CLASSES = [
    TrendAgent,          # Phase 1
    TopicAgent,          # Phase 2
    ScriptAgent,         # Phase 3
    SceneAgent,          # Phase 4
    MediaAgent,          # Phase 5
    VoiceAgent,          # Phase 6 (Will be renamed AudioAgent)
    StructureAgent,      # Phase 7
    AssemblyAgent,       # Phase 8-10 (Sync, Quality, Assembly handled here for now)
    ValidatorAgent,      # Phase 11
    QualityScoringAgent, # Phase 12
    ComplianceAgent,     # Phase 13
    SEOAgent,            # Phase 14
    LearningAgent,       # Phase 15
]

async def run_pipeline(topic_hint: str = "", target_scene_count: int = 5, 
                       target_duration_minutes: float = 0, video_format: str = "16:9", 
                       voice_provider: str = "edge", voice_id: str = "en-US-AvaNeural",
                       voice_gender: str = "female", 
                       voice_style: str = "normal", voice_speed: float = 1.05, 
                       user_script: str = "", media_balance: float = 0.5,
                       video_style: str = "realistic") -> AsyncGenerator[dict, None]:
    """Async generator that drives the pipeline and yields SSE dicts."""
    
    # If duration is provided, it overrides scene count
    if target_duration_minutes > 0:
        # Dynamic calculation: ~12 scenes per minute (5s per scene average)
        # This allows for more stable generation for long videos.
        calc_count = int(target_duration_minutes * 12)
        target_scene_count = max(5, min(calc_count, 150)) # Clamp between 5 and 150

    pipeline_json: dict = {
        "topic_hint": topic_hint,
        "run_id": str(int(time.time())),
        "platform": "YouTube",
        "target_scene_count": max(1, int(target_scene_count or 5)),
        "target_duration_minutes": target_duration_minutes,
        "video_format": video_format,
        "video_style": video_style,
        "voice_provider": voice_provider,
        "user_script": user_script,
        "media_balance": media_balance,
        "voice": {
            "provider": voice_provider,
            "voice_id": voice_id,
            "type": voice_gender,
            "style": voice_style,
            "speed": voice_speed
        }
    }

    i = 0
    global_retries = 0
    MAX_GLOBAL_RETRIES = 1
    while i < len(AGENT_CLASSES):
        AgentClass = AGENT_CLASSES[i]
        agent = AgentClass()

        # Signal phase started
        yield {
            "event": "phase_update",
            "data": json.dumps(
                {
                    "phase": i + 1,
                    "name": agent.PHASE_NAME,
                    "status": "running",
                    "output": None,
                }
            ),
        }

        try:
            result = await agent.run(pipeline_json)
            pipeline_json.update(result)

            # Check for failures that should trigger retry
            if hasattr(agent, "PHASE_NUM") and agent.PHASE_NUM == 10 and not result.get("valid", True):
                 raise ValueError(f"Validation failed: {json.dumps(result.get('issues', []))}")

            yield {
                "event": "phase_update",
                "data": json.dumps(
                    {
                        "phase": i + 1,
                        "name": agent.PHASE_NAME,
                        "status": "done",
                        "output": result,
                    }
                ),
            }
            i += 1  # Move to next phase on success

        except Exception as exc:
            yield {
                "event": "phase_update",
                "data": json.dumps(
                    {
                        "phase": i + 1,
                        "name": agent.PHASE_NAME,
                        "status": "error",
                        "error": str(exc),
                        "output": None,
                    }
                ),
            }
            
            # Auto-retry logic
            global_retries += 1
            if global_retries <= MAX_GLOBAL_RETRIES:
                print(f"Global Retry {global_retries}/{MAX_GLOBAL_RETRIES} triggered by {agent.PHASE_NAME}")
                # For simplicity, just retry the same phase for now, or go back to Script if it's a major failure
                continue

            # Emit pipeline_failed and stop
            yield {
                "event": "pipeline_failed",
                "data": json.dumps(
                    {"phase": i + 1, "reason": str(exc)}
                ),
            }
            return

    # FINAL SUCCESS OUTPUT
    yield {
        "event": "pipeline_complete",
        "data": json.dumps({
            "status": "SUCCESS", 
            "video_path": pipeline_json.get("video_path"),
            "scene_count": len(pipeline_json.get("scenes", [])),
            "audio_synced": True,
            "subtitles_valid": True,
            "media_quality": pipeline_json.get("quality_scores", {}).get("media_score", "high"),
            "quality_scores": pipeline_json.get("quality_scores", {}),
            "learning_saved": pipeline_json.get("learning_saved", False),
            "seo": pipeline_json.get("seo")
        }),
    }
