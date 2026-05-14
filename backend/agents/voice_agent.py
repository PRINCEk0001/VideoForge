"""
Phase 7 — Voice Agent
Generates ONE audio clip per scene from each scene's narration text.
Files saved to: downloads/audio/scene_1.mp3 … scene_N.mp3

TTS Tier Order: Unreal Speech → ElevenLabs → gTTS (always falls through)
"""
import os
import io
import httpx
from backend.agents.base_agent import BaseAgent
import asyncio
import edge_tts

# Force local model cache to avoid global downloads
LOCAL_MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../downloads/models/hf_cache"))
os.environ["HF_HOME"] = LOCAL_MODELS_DIR
os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)

AUDIO_DIR = "downloads/audio"


# ── TTS helper (Free Edge-TTS) ───────────────────────────────────────────────

# ── TTS voice configurations ───────────────────────────────────────────────

VOICE_MAP = {
    "edge": {
        "female": {
            "name": "Ava (Fast)",
            "id": "en-US-AvaNeural",
        },
        "male": {
            "name": "Andrew (Fast)",
            "id": "en-US-AndrewNeural",
        },
        "energetic": {
            "name": "Emma (Fast)",
            "id": "en-US-EmmaNeural",
        }
    },
    "eleven": {
        "female": {
            "name": "Rachel (Premium)",
            "id": "21m00Tcm4TlvDq8ikWAM",
        },
        "male": {
            "name": "Adam (Premium)",
            "id": "pNInz6obpgDQGcFmaJgB",
        },
        "professional": {
            "name": "Josh (Premium)",
            "id": "TxGEqnHW47ic4qpgms3u",
        }
    },
    "unreal": {
        "female": {
            "name": "Scarlett (High Quality)",
            "id": "Scarlett",
        },
        "male": {
            "name": "Will (High Quality)",
            "id": "Will",
        }
    },
    "kokoro": {
        "female": {
            "name": "Heart (Local Free)",
            "id": "af_heart",
        },
        "male": {
            "name": "George (Local Free)",
            "id": "bm_george",
        }
    }
}

async def _tts_edge(text: str, voice_id: str, speed: float = 1.0) -> bytes | None:
    """High-quality Microsoft Edge Neural TTS (Free)."""
    try:
        rate_val = int((speed - 1.0) * 100)
        rate_str = f"{rate_val:+}%" if rate_val != 0 else "+0%"
        
        communicate = edge_tts.Communicate(text, voice_id, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        if len(audio_data) > 100:
            return audio_data
    except Exception as e:
        print(f"[VoiceAgent] Edge-TTS error: {e}")
    return None

async def _tts_kokoro(text: str, voice_id: str) -> bytes | None:
    """Free local High-Quality Kokoro TTS."""
    try:
        from kokoro import KPipeline
        import soundfile as sf
        import io
        
        # Initialize pipeline (cached)
        if not hasattr(_tts_kokoro, "pipeline"):
            _tts_kokoro.pipeline = KPipeline(lang_code='a')
            
        generator = _tts_kokoro.pipeline(text, voice=voice_id, speed=1, split_pattern=r'\n+')
        
        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)
            
        if not audio_chunks:
            return None
            
        import numpy as np
        combined_audio = np.concatenate(audio_chunks)
        
        # Convert to MP3/WAV bytes
        buf = io.BytesIO()
        sf.write(buf, combined_audio, 24000, format='WAV')
        return buf.getvalue()
    except Exception as e:
        print(f"[VoiceAgent] Kokoro exception (ensure 'kokoro' and 'soundfile' are installed): {e}")
    return None



def _measure_duration(path: str) -> float:
    """Return audio duration in seconds using mutagen or ffmpeg fallback."""
    try:
        from mutagen.mp3 import MP3
        return MP3(path).info.length
    except Exception:
        pass
    try:
        import subprocess
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        r = subprocess.run([ff, "-i", path], capture_output=True, text=True)
        for line in r.stderr.splitlines():
            if "Duration:" in line:
                ds = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = ds.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return 3.0  # safe default


class VoiceAgent(BaseAgent):
    PHASE_NUM  = 5
    PHASE_NAME = "Audio Generation"

    async def _tts_elevenlabs(self, text: str, voice_id: str, client: httpx.AsyncClient) -> bytes | None:
        """Premium ElevenLabs TTS."""
        if not self.elevenlabs_key:
            return None
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            resp = await client.post(
                url,
                headers={"xi-api-key": self.elevenlabs_key, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                },
                timeout=30
            )
            if resp.status_code == 200:
                return resp.content
            print(f"[VoiceAgent] ElevenLabs error: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[VoiceAgent] ElevenLabs exception: {e}")
        return None

    async def _tts_unreal(self, text: str, voice_id: str, client: httpx.AsyncClient) -> bytes | None:
        """Fast Unreal Speech TTS."""
        if not self.unreal_key:
            return None
        try:
            url = "https://api.unrealspeech.com/stream"
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {self.unreal_key}", "Content-Type": "application/json"},
                json={
                    "Text": text,
                    "VoiceId": voice_id,
                    "Bitrate": "192k",
                    "Speed": 0, # Unreal uses -1 to 1 for speed
                    "Pitch": 0
                },
                timeout=30
            )
            if resp.status_code == 200:
                return resp.content
            print(f"[VoiceAgent] Unreal Speech error: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[VoiceAgent] Unreal Speech exception: {e}")
        return None

    async def _generate_audio(self, text: str, client: httpx.AsyncClient, config: dict) -> bytes:
        """Generate audio with multi-provider support and automatic fallbacks."""
        provider = config.get("provider", "edge")
        voice_id = config.get("voice_id")
        speed = float(config.get("speed", 1.05))

        data = None
        for attempt in range(2):
            try:
                if provider == "eleven":
                    data = await self._tts_elevenlabs(text, voice_id, client)
                elif provider == "unreal":
                    data = await self._tts_unreal(text, voice_id, client)
                elif provider == "kokoro":
                    # Kokoro uses too much RAM for Render free tier (512MB limit)
                    # We disable it by default to prevent OOM
                    print("[VoiceAgent] Kokoro skipped to save memory. Use Edge/ElevenLabs instead.")
                    data = None
                elif provider == "edge":
                    data = await _tts_edge(text, voice_id, speed)
                
                if data:
                    return data
            except Exception as e:
                print(f"[VoiceAgent] Attempt {attempt+1} failed for {provider}: {e}")
            
            if attempt == 0:
                await asyncio.sleep(1)

        # Final Fallback
        fallback_voice = "en-US-AvaNeural"
        data = await _tts_edge(text, fallback_voice, speed)
        if data:
            return data

        raise RuntimeError("All TTS providers failed.")

    async def run(self, pipeline_json: dict) -> dict:
        scenes = pipeline_json.get("scenes", [])
        os.makedirs(AUDIO_DIR, exist_ok=True)
        os.makedirs("downloads", exist_ok=True)

        scene_audio_paths: list[str | None] = []
        scene_durations:   list[float]      = []
        
        voice_config = pipeline_json.get("voice", {})
        
        async with httpx.AsyncClient() as client:
            for idx, scene in enumerate(scenes, 1):
                # Stagger requests slightly to avoid rate limits
                if idx > 1:
                    await asyncio.sleep(0.3)
                
                narration = (scene.get("text") or "").strip()
                if not narration:
                    narration = f"Scene {idx} of the video."

                dest = os.path.join(AUDIO_DIR, f"scene_{idx}.mp3")

                try:
                    audio_bytes = await self._generate_audio(narration, client, voice_config)
                    with open(dest, "wb") as f:
                        f.write(audio_bytes)
                    dur = _measure_duration(dest)
                    scene_audio_paths.append(dest)
                    scene_durations.append(dur)

                except Exception as e:
                    print(f"[VoiceAgent] Scene {idx} audio FAILED: {e}")
                    scene_audio_paths.append(None)
                    scene_durations.append(float(scene.get("duration", 3)))

        # Update each scene's duration to match its actual audio length
        updated_scenes = [
            {**scene, "duration": round(dur, 3)}
            for scene, dur in zip(scenes, scene_durations)
        ]

        return {
            "scenes":            updated_scenes,
            "scene_audio_paths": scene_audio_paths,
            "scene_durations":   scene_durations,
            "audio_generated":   True,
        }
