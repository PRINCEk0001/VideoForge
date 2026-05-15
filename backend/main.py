"""
FastAPI application entry point.
Endpoints:
  GET /api/run            — SSE stream, runs the full pipeline in background
  GET /api/health         — Health check
  GET /api/download_video — Download the single final_video.mp4
  GET /api/projects       — List all saved projects
  GET /api/analytics      — Get aggregate stats
"""
import os
import json
import httpx
import uuid
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from backend import orchestrator
from backend.utils.config_manager import ConfigManager

# Ensure local model cache and storage directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend/dist")
STORAGE_DIRS = ["downloads/scenes", "downloads/audio", "downloads/synced", "output", "downloads/models/hf_cache"]

for d in STORAGE_DIRS:
    path = os.path.join(BASE_DIR, d)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

os.environ["HF_HOME"] = os.path.join(BASE_DIR, "downloads/models/hf_cache")

app = FastAPI(title="VideoForge AI", version="2.0.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # This allows Hugging Face to display the app in their iframe
    response.headers["Content-Security-Policy"] = "frame-ancestors https://*.huggingface.co https://huggingface.co"
    return response

# Temporary store for run configurations (BYOK security)
run_store = {}

class RunConfig(BaseModel):
    topic_hint: str = ""
    target_scene_count: int = 5
    target_duration_minutes: float = 0
    video_format: str = "16:9"
    voice_provider: str = "edge"
    voice_id: str = ""
    voice_speed: float = 1.05
    user_script: str = ""
    media_balance: float = 0.5
    video_style: str = "realistic"
    # Keys
    gemini_key: str | None = None
    groq_key: str | None = None
    pexels_key: str | None = None
    pixabay_key: str | None = None
    elevenlabs_key: str | None = None
    unreal_key: str | None = None

@app.post("/api/run/init")
async def init_run(config: RunConfig):
    run_id = str(uuid.uuid4())
    run_store[run_id] = config
    return {"run_id": run_id}

@app.get("/api/run/stream/{run_id}")
async def run_pipeline_endpoint(run_id: str):
    if run_id not in run_store:
        raise HTTPException(status_code=404, detail="Run not initialized or expired")
    
    config = run_store.pop(run_id) # Use and remove for security
    
    request_keys = {
        "gemini_api": config.gemini_key,
        "groq_api": config.groq_key,
        "pexels_api": config.pexels_key,
        "pixabay_api": config.pixabay_key,
        "elevenlabs_api": config.elevenlabs_key,
        "unreal_speech_api": config.unreal_key,
    }
    
    return EventSourceResponse(
        orchestrator.run_pipeline_iterative(
            topic_hint=config.topic_hint,
            target_scene_count=config.target_scene_count,
            target_duration_minutes=config.target_duration_minutes,
            video_format=config.video_format,
            voice_provider=config.voice_provider,
            voice_id=config.voice_id,
            voice_speed=config.voice_speed,
            user_script=config.user_script,
            media_balance=config.media_balance,
            video_style=config.video_style,
            request_keys=request_keys
        )
    )

FINAL_VIDEO = "downloads/final_video.mp4"

# Shared HTTP client for efficiency
_shared_client = httpx.AsyncClient(timeout=30)

@app.get("/api/voice_preview")
async def voice_preview(
    text: str = Query(default="Hello, this is a sample of my voice. Do you like it?", description="Text to speak"),
    provider: str = Query(default="edge"),
    voice_id: str = Query(default="en-US-AvaNeural"),
    speed: float = Query(default=1.0)
):
    """
    Generate a short audio preview for a specific voice.
    Uses StreamingResponse for instant playback.
    """
    from backend.agents.voice_agent import _tts_edge, _tts_elevenlabs, _tts_unreal, _tts_kokoro
    from fastapi.responses import StreamingResponse
    import io

    try:
        config = {"provider": provider, "voice_id": voice_id, "speed": speed}
        
        # For Edge TTS, we can stream directly
        if provider == "edge":
            import edge_tts
            rate_val = int((speed - 1.0) * 100)
            rate_str = f"{rate_val:+}%" if rate_val != 0 else "+0%"
            communicate = edge_tts.Communicate(text, voice_id, rate=rate_str)
            
            async def edge_generator():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        yield chunk["data"]
            
            return StreamingResponse(edge_generator(), media_type="audio/mpeg")

        # For others, we generate then stream
        from backend.agents.voice_agent import _generate_audio
        audio_bytes = await _generate_audio(text, _shared_client, config)
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

    except Exception as e:
        print(f"[Preview Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    from datetime import datetime
    return {
        "status": "OK",
        "message": "Your API is running",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/check_voice")
async def check_voice_api(provider: str = Query("unreal")):
    """Tests the selected voice provider API key."""
    provider = provider.lower()
    if provider in ["gtts", "edgetts"]:
        return {"ok": True, "message": "Edge TTS (free) is always available."}
        
    async with httpx.AsyncClient() as client:
        if provider == "unreal":
            key = ConfigManager.get_api_key("unreal_speech_api") or os.getenv("UNREAL_SPEECH_API_KEY", "")
            if not key: return {"ok": False, "message": "Unreal Speech API key missing (check Settings or .env)"}
            try:
                # Fast auth check
                resp = await client.post(
                    "https://api.unrealspeech.com/stream",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"Text": "Test", "VoiceId": "Will", "Bitrate": "192k"},
                    timeout=5
                )
                if resp.status_code == 200: return {"ok": True, "message": "Unreal Speech API is working!"}
                return {"ok": False, "message": f"Unreal Speech API Error: HTTP {resp.status_code}"}
            except Exception as e:
                return {"ok": False, "message": f"Unreal Connection Error: {e}"}
                
        elif provider == "elevenlabs":
            key = ConfigManager.get_api_key("elevenlabs_api") or os.getenv("ELEVENLABS_API_KEY", "")
            if not key: return {"ok": False, "message": "ElevenLabs API key missing (check Settings or .env)"}
            try:
                # Get models endpoint is a free way to verify the API key
                resp = await client.get(
                    "https://api.elevenlabs.io/v1/models",
                    headers={"xi-api-key": key},
                    timeout=5
                )
                if resp.status_code == 200: return {"ok": True, "message": "ElevenLabs API is working!"}
                return {"ok": False, "message": f"ElevenLabs API Error: HTTP {resp.status_code}"}
            except Exception as e:
                return {"ok": False, "message": f"ElevenLabs Connection Error: {e}"}
    
    return {"ok": False, "message": f"Unknown provider {provider}"}


class VerifyConfig(BaseModel):
    provider: str
    key: str

@app.post("/api/config/verify")
async def verify_key_endpoint(config: VerifyConfig):
    """Verify an API key before saving it."""
    provider = config.provider
    key = config.key
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            if provider == "gemini":
                # Test with a simple request
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                resp = await client.get(url)
                if resp.status_code == 200: return {"ok": True, "message": "Gemini key is valid!"}
                return {"ok": False, "message": f"Gemini Error: {resp.json().get('error', {}).get('message', 'Invalid Key')}"}
            
            if provider == "groq":
                url = "https://api.groq.com/openai/v1/models"
                resp = await client.get(url, headers={"Authorization": f"Bearer {key}"})
                if resp.status_code == 200: return {"ok": True, "message": "Groq key is valid!"}
                return {"ok": False, "message": "Invalid Groq Key"}

            if provider == "pexels":
                url = "https://api.pexels.com/v1/search?query=test&per_page=1"
                resp = await client.get(url, headers={"Authorization": key})
                if resp.status_code == 200: return {"ok": True, "message": "Pexels key is valid!"}
                return {"ok": False, "message": "Invalid Pexels Key"}

            if provider == "pixabay":
                url = f"https://pixabay.com/api/?key={key}&q=test"
                resp = await client.get(url)
                if resp.status_code == 200: return {"ok": True, "message": "Pixabay key is valid!"}
                return {"ok": False, "message": "Invalid Pixabay Key"}

            if provider == "elevenlabs":
                url = "https://api.elevenlabs.io/v1/user"
                resp = await client.get(url, headers={"xi-api-key": key})
                if resp.status_code == 200: return {"ok": True, "message": "ElevenLabs key is valid!"}
                return {"ok": False, "message": "Invalid ElevenLabs Key"}

            if provider == "unreal":
                # Unreal Speech doesn't have a simple profile endpoint, test with a small synth
                url = "https://api.unrealspeech.com/stream"
                resp = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json={"Text": "t", "VoiceId": "Dan"})
                if resp.status_code in [200, 400]: return {"ok": True, "message": "Unreal Speech key is valid!"} # 400 is fine if it reached the server
                return {"ok": False, "message": "Invalid Unreal Speech Key"}

            return {"ok": False, "message": f"Verification not implemented for {provider}"}
        except Exception as e:
            return {"ok": False, "message": f"Verification failed: {str(e)}"}

class APIKeysModel(BaseModel):
    groq_api: str | None = None
    gemini_api: str | None = None
    pexels_api: str | None = None
    pixabay_api: str | None = None
    elevenlabs_api: str | None = None
    unreal_speech_api: str | None = None

@app.post("/api/config/keys")
async def save_keys(keys: APIKeysModel):
    ConfigManager.save_api_keys(keys.model_dump(exclude_none=True))
    return {"status": "ok", "message": "Keys encrypted and saved."}

@app.get("/api/config/keys")
async def get_keys():
    return ConfigManager.get_masked_keys()

class UserPreferencesModel(BaseModel):
    preferred_voice: str | None = None
    preferred_style: str | None = None
    preferred_pacing: str | None = None
    preferred_media_mode: str | None = None
    subtitle_style: str | None = None

@app.post("/api/config/preferences")
async def save_prefs(prefs: UserPreferencesModel):
    ConfigManager.save_preferences(prefs.model_dump(exclude_none=True))
    return {"status": "ok", "message": "Preferences saved."}

@app.get("/api/config/preferences")
async def get_prefs():
    return ConfigManager.load_preferences()

@app.get("/api/download_video")
async def download_video():
    """
    Serve the single final video file.
    This is the ONLY file the user ever downloads.
    It contains all scenes with synced narration audio — ready to watch.
    """
    if not os.path.exists(FINAL_VIDEO):
        raise HTTPException(
            status_code=404,
            detail="Video not ready yet. Run the pipeline first."
        )
    if os.path.getsize(FINAL_VIDEO) == 0:
        raise HTTPException(
            status_code=500,
            detail="Video file is empty — pipeline may have failed."
        )
    return FileResponse(
        FINAL_VIDEO,
        media_type="video/mp4",
        filename="final_video.mp4",
        headers={"Content-Disposition": "attachment; filename=final_video.mp4"},
    )

@app.get("/api/projects")
async def list_projects():
    """List all projects in the output directory."""
    output_dir = "output"
    if not os.path.exists(output_dir):
        return []
    
    projects = []
    for f in os.listdir(output_dir):
        if f.endswith(".json"):
            try:
                with open(os.path.join(output_dir, f), "r", encoding="utf-8") as meta_f:
                    projects.append(json.load(meta_f))
            except:
                pass
    
    # Sort by date descending
    projects.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return projects

@app.get("/api/projects/{project_id}/video")
async def get_project_video(project_id: str):
    """Serve a specific project video."""
    video_path = f"output/project_{project_id}.mp4"
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Project video not found.")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"video_{project_id}.mp4"
    )

@app.get("/api/analytics")
async def get_analytics():
    """Calculate aggregate stats from all projects."""
    output_dir = "output"
    if not os.path.exists(output_dir):
        return {"total_videos": 0, "avg_retention": "0%", "avg_seo": 0, "total_duration_mins": 0, "history": []}
    
    projects = []
    for f in os.listdir(output_dir):
        if f.endswith(".json"):
            try:
                with open(os.path.join(output_dir, f), "r", encoding="utf-8") as meta_f:
                    projects.append(json.load(meta_f))
            except: pass
            
    if not projects:
        return {"total_videos": 0, "avg_retention": "0%", "avg_seo": 0, "total_duration_mins": 0, "history": []}
    
    total_videos = len(projects)
    total_seo = sum(p.get("seo_score", 0) for p in projects)
    total_dur_secs = sum(p.get("duration", 0) for p in projects)
    
    # Simulated retention based on SEO score and duration
    avg_retention = sum(min(95, p.get("seo_score", 80) - 5) for p in projects) / total_videos

    return {
        "total_videos": total_videos,
        "avg_retention": f"{int(avg_retention)}%",
        "avg_seo": int(total_seo / total_videos),
        "total_duration_mins": round(total_dur_secs / 60, 1),
        "history": [p.get("seo_score", 85) for p in projects[:7]][::-1] # Last 7 projects
    }

@app.get("/api/debug/paths")
async def debug_paths():
    """Diagnostic endpoint to check filesystem on Render."""
    try:
        frontend_path = os.path.join(BASE_DIR, "frontend")
        dist_path = os.path.join(frontend_path, "dist")
        
        return {
            "cwd": os.getcwd(),
            "base_dir": BASE_DIR,
            "base_exists": os.path.exists(BASE_DIR),
            "frontend_exists": os.path.exists(frontend_path),
            "dist_exists": os.path.exists(dist_path),
            "dist_contents": os.listdir(dist_path) if os.path.exists(dist_path) else [],
            "frontend_contents": os.listdir(frontend_path) if os.path.exists(frontend_path) else [],
            "env_port": os.getenv("PORT"),
            "hf_home": os.getenv("HF_HOME")
        }
    except Exception as e:
        return {"error": str(e)}

# ── Serve Frontend ────────────────────────────────────────────────────────────
# This MUST be the last part of the file to avoid shadowing API routes.
if os.path.exists(FRONTEND_DIST):
    # This handles assets, favicon, and index.html (via html=True)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    print(f"[Warning] Frontend dist directory not found at {FRONTEND_DIST}")
