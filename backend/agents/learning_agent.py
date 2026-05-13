import os
import json
import time
from backend.agents.base_agent import BaseAgent

LEARNING_DIR = "learning"
SCORES_DIR = os.path.join(LEARNING_DIR, "scores")
HISTORY_DIR = os.path.join(LEARNING_DIR, "history")

class LearningAgent(BaseAgent):
    PHASE_NUM = 15
    PHASE_NAME = "Learning & Adaptation"

    def __init__(self):
        super().__init__()
        os.makedirs(SCORES_DIR, exist_ok=True)
        os.makedirs(HISTORY_DIR, exist_ok=True)

    async def run(self, pipeline_json: dict) -> dict:
        """Saves successful patterns and metrics for future runs."""
        run_id = pipeline_json.get("run_id", str(int(time.time())))
        
        # Extract meaningful data to learn from
        learning_data = {
            "run_id": run_id,
            "timestamp": time.time(),
            "topic": pipeline_json.get("selected_topic"),
            "format": pipeline_json.get("video_format"),
            "scene_count": len(pipeline_json.get("scenes", [])),
            "media_scores": [m.get("score") for m in pipeline_json.get("media", [])],
            "quality_scores": pipeline_json.get("quality_scores", {}),
            "status": "SUCCESS" if pipeline_json.get("video_path") else "FAILED"
        }

        # Save to history
        history_path = os.path.join(HISTORY_DIR, f"run_{run_id}.json")
        try:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(learning_data, f, indent=2)
        except Exception as e:
            print(f"[LearningAgent] Failed to save history: {e}")

        # If successful and scores are good, append to a 'successful_patterns' DB
        # This is a stub for future RL or pattern matching
        if learning_data["status"] == "SUCCESS":
            avg_media_score = sum(learning_data["media_scores"]) / max(1, len(learning_data["media_scores"]))
            if avg_media_score > 0.7:
                pattern_path = os.path.join(SCORES_DIR, "successful_patterns.jsonl")
                try:
                    with open(pattern_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "topic": learning_data["topic"],
                            "avg_media_score": avg_media_score,
                            "run_id": run_id
                        }) + "\n")
                except: pass

        return {
            "learning_saved": True,
            "learning_data": learning_data
        }
