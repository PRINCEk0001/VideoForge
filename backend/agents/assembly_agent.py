import os
import glob
import shutil
import subprocess
import textwrap

from backend.agents.base_agent import BaseAgent

# ── FFmpeg ────────────────────────────────────────────────────────────────────
try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_BIN = "ffmpeg"

SCENES_DIR   = "downloads/scenes"
AUDIO_DIR    = "downloads/audio"
SYNCED_DIR   = "downloads/synced"
OUTPUT_PATH  = "downloads/final_video.mp4"
CONCAT_LIST  = "downloads/_concat_list.txt"
BG_MUSIC     = "downloads/music.mp3"  # Optional background music


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(args: list) -> subprocess.CompletedProcess:
    """Run ffmpeg, raise RuntimeError on failure."""
    cmd = [FFMPEG_BIN, "-y"] + args
    # print(f"[FFmpeg] {' '.join(str(x) for x in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (code {result.returncode}):\n{result.stderr[-2000:]}"
        )
    return result


def _duration(path: str) -> float:
    """Return duration in seconds, 0.0 on failure."""
    r = subprocess.run([FFMPEG_BIN, "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            ds = line.split("Duration:")[1].split(",")[0].strip()
            try:
                h, m, s = ds.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                return 0.0
    return 0.0


def _generate_ass_subtitles(text: str, duration: float, out_path: str, video_format: str = "16:9"):
    """Generate a stylized .ass subtitle file for a single scene."""
    is_short = (video_format == "9:16")
    
    # Adaptive settings
    max_words_per_line = 3 if is_short else 6
    play_res_x = 1080 if is_short else 1920
    play_res_y = 1920 if is_short else 1080
    font_size = 110 if is_short else 75
    outline_size = 6 if is_short else 3
    alignment = 5 if is_short else 2
    margin_v = 30 if is_short else 80

    # Split text into lines
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        if len(current_line) < max_words_per_line:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    
    # Take max 2 lines for this specific subtitle chunk
    final_lines = lines[:2]
    wrapped = "\\N".join(final_lines)
    
    # ASS Header & Styles
    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,{outline_size},0,{alignment},30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{_fmt_ass_time(duration)},Default,,0,0,0,,{wrapped}
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

def _fmt_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ── Per-scene sync ────────────────────────────────────────────────────────────

def _build_video_segment(video_path: str | None, duration: float, tmp_prefix: str, video_format: str = "16:9") -> str:
    """
    Return path to a silent H.264/1920x1080/24fps video segment
    exactly `duration` seconds long.
    """
    out = f"{tmp_prefix}_video_only.mp4"

    if video_format == "9:16":
        res = "1080:1920"
        pad = "1080:1920"
        scale = "1080x1920"
    else:
        res = "1920:1080"
        pad = "1920:1080"
        scale = "1920x1080"

    if video_path and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        is_image = video_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))

        if is_image:
            # Apply Ken Burns effect (slow dynamic zoom)
            _run([
                "-loop", "1",
                "-i", video_path,
                "-t", f"{duration:.4f}",
                "-vf", (
                    f"scale=4000:-1,"  # optimal for 1080p zoom
                    f"zoompan=z='min(zoom+0.0015,1.5)':d={int(duration * 24 + 100)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={scale},"
                    f"setsar=1"
                ),
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-r", "24", "-pix_fmt", "yuv420p",
                "-an", out,
            ])
        else:
            # Video file: loop as many times as needed, then trim
            vid_dur = _duration(video_path)
            if vid_dur <= 0:
                vid_dur = 1.0
            loops = max(2, int(duration / vid_dur) + 2)
            _run([
                "-stream_loop", str(loops),
                "-i", video_path,
                "-t", f"{duration:.4f}",
                "-vf", (
                    f"scale={res}:force_original_aspect_ratio=decrease,"
                    f"pad={pad}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
                ),
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-r", "24", "-pix_fmt", "yuv420p",
                "-an", out,
            ])
    else:
        # No asset → dark background
        _run([
            "-f", "lavfi",
            "-i", f"color=c=0x0d1117:size={scale}:rate=24:duration={duration:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an", out,
        ])

    return out


def _sync_scene(idx: int, video_path: str | None,
                audio_path: str | None, fallback_dur: float, 
                subtitle_text: str = "", video_format: str = "16:9") -> str:
    """
    Produce one perfectly-synced scene clip with subtitles:
      - video loops/trims to match the narration audio duration
      - narration audio is attached starting at t=0
      - subtitles overlay the video
    """
    os.makedirs(SYNCED_DIR, exist_ok=True)
    prefix = os.path.join(SYNCED_DIR, f"scene_{idx}")
    out    = f"{prefix}_synced.mp4"
    ass_path = f"{prefix}.ass"

    # Determine exact duration from audio
    if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        audio_dur = _duration(audio_path)
        if audio_dur <= 0:
            audio_dur = fallback_dur
    else:
        audio_dur  = fallback_dur
        audio_path = None

    # Step A: build silent video segment
    video_only = _build_video_segment(video_path, audio_dur, prefix, video_format)

    # Step B: Generate Subtitles
    if subtitle_text:
        _generate_ass_subtitles(subtitle_text, audio_dur, ass_path, video_format)
        # Use simple escaping for Windows paths in FFmpeg filter
        escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
        video_filter = f"subtitles='{escaped_ass}'"
    else:
        video_filter = "copy"

    # Step C: mux audio and overlay subtitles
    if audio_path:
        args = [
            "-i", video_only,
            "-i", audio_path,
        ]
        
        # Audio processing
        filter_complex = f"[1:a]apad=pad_dur={audio_dur + 1:.4f}[ap];[ap]atrim=0:{audio_dur:.4f},asetpts=PTS-STARTPTS[a]"
        
        if subtitle_text:
            args.extend(["-vf", video_filter])
            args.extend(["-filter_complex", filter_complex])
            args.extend(["-map", "0:v", "-map", "[a]"])
            args.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"])
        else:
            args.extend(["-filter_complex", filter_complex])
            args.extend(["-map", "0:v", "-map", "[a]"])
            args.extend(["-c:v", "copy"])
            
        args.extend([
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-t", f"{audio_dur:.4f}",
            out
        ])
        _run(args)
    else:
        # Silence
        args = [
            "-i", video_only,
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        ]
        if subtitle_text:
            args.extend(["-vf", video_filter])
            args.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"])
        else:
            args.extend(["-c:v", "copy"])
            
        args.extend([
            "-map", "0:v", "-map", "1:a",
            "-c:a", "aac", "-b:a", "128k",
            "-t", f"{audio_dur:.4f}",
            out
        ])
        _run(args)

    # Cleanup
    for tmp in [video_only, ass_path]:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

    return out


# ── Concat + Background Music ──────────────────────────────────────────────────

def _concat_all(synced_files: list[str]) -> None:
    """Concatenate all synced scene files and optionally add background music."""
    with open(CONCAT_LIST, "w", encoding="utf-8") as f:
        for sf in synced_files:
            escaped = os.path.abspath(sf).replace("\\", "/")
            f.write(f"file '{escaped}'\n")

    # If background music exists, mix it in
    if os.path.exists(BG_MUSIC) and os.path.getsize(BG_MUSIC) > 0:
        print(f"[Assembly] Mixing background music: {BG_MUSIC}")
        # Concat first, then mix
        temp_merged = "downloads/_temp_merged.mp4"
        _run([
            "-f", "concat", "-safe", "0",
            "-i", CONCAT_LIST,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            temp_merged
        ])
        
        dur = _duration(temp_merged)
        
        # Mix audio: background music at 15% volume, narration at 100%
        _run([
            "-i", temp_merged,
            "-stream_loop", "-1", "-i", BG_MUSIC,
            "-filter_complex", 
            f"[1:a]volume=0.15,atrim=0:{dur},asetpts=PTS-STARTPTS[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart",
            OUTPUT_PATH
        ])
        if os.path.exists(temp_merged):
            os.remove(temp_merged)
    else:
        _run([
            "-f", "concat", "-safe", "0",
            "-i", CONCAT_LIST,
            "-c", "copy",
            "-movflags", "+faststart",
            OUTPUT_PATH,
        ])


def _purge_temp_files() -> None:
    """Delete intermediate files."""
    for d in [SYNCED_DIR, AUDIO_DIR]:
        if os.path.isdir(d):
            try: shutil.rmtree(d)
            except: pass

    # List of individual temp files to remove
    temp_files = [
        CONCAT_LIST, 
        "downloads/temp-audio.m4a",
        "downloads/_temp_merged.mp4",
        "downloads/_concat_list.txt"
    ]
    for f in temp_files:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    if os.path.isdir(SCENES_DIR):
        try: shutil.rmtree(SCENES_DIR)
        except: pass


# ── Agent ─────────────────────────────────────────────────────────────────────

class AssemblyAgent(BaseAgent):
    PHASE_NUM  = 9
    PHASE_NAME = "Final Assembly"

    async def run(self, pipeline_json: dict) -> dict:
        scenes            = pipeline_json.get("scenes", [])
        media_list        = pipeline_json.get("media", [])
        scene_audio_paths = pipeline_json.get("scene_audio_paths", [])
        scene_durations   = pipeline_json.get("scene_durations", [])
        video_format      = pipeline_json.get("video_format", "16:9")

        if not scenes:
            return {"video_created": False, "error": "No scenes in pipeline."}

        os.makedirs(SYNCED_DIR, exist_ok=True)
        os.makedirs("downloads", exist_ok=True)

        print(f"[Assembly] Starting per-scene A/V sync + Subtitles for {len(scenes)} scene(s)...")
        synced_files = []

        for idx, scene in enumerate(scenes, 1):
            # Locate video file
            video_path = None
            for ext in (".mp4", ".jpg", ".jpeg", ".png", ".webp"):
                candidate = os.path.join(SCENES_DIR, f"scene_{idx}{ext}")
                if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                    video_path = candidate
                    break
            if not video_path and (idx - 1) < len(media_list):
                lp = (media_list[idx - 1] or {}).get("local_path")
                if lp and os.path.exists(lp) and os.path.getsize(lp) > 0:
                    video_path = lp

            # Locate audio file
            audio_path = None
            if (idx - 1) < len(scene_audio_paths):
                ap = scene_audio_paths[idx - 1]
                if ap and os.path.exists(ap) and os.path.getsize(ap) > 0:
                    audio_path = ap
            if not audio_path:
                candidate = os.path.join(AUDIO_DIR, f"scene_{idx}.mp3")
                if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                    audio_path = candidate

            # Subtitle text
            subtitle_text = scene.get("text", "")

            # Sync scene
            try:
                synced = _sync_scene(idx, video_path, audio_path, 3.0, subtitle_text, video_format)
                synced_files.append(synced)
            except Exception as e:
                print(f"[Assembly] Scene {idx} sync FAILED: {e}")
                try:
                    synced = _sync_scene(idx, None, None, 3.0, subtitle_text, video_format)
                    synced_files.append(synced)
                except: pass

        if not synced_files:
            return {"video_created": False, "error": "No scenes assembled."}

        print(f"[Assembly] Concatenating + Music -> {OUTPUT_PATH}")
        try:
            _concat_all(synced_files)
        except Exception as e:
            return {"video_created": False, "error": f"Concat failed: {e}"}

        if not os.path.exists(OUTPUT_PATH) or os.path.getsize(OUTPUT_PATH) == 0:
            return {"video_created": False, "error": "Output file missing/empty."}

        final_dur = _duration(OUTPUT_PATH)
        final_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
        
        _purge_temp_files()

        return {
            "video_created":   True,
            "video_path":      OUTPUT_PATH,
            "actual_duration": round(final_dur, 3),
            "scene_count":     len(synced_files),
            "file_size_mb":    round(final_size_mb, 1),
            "sync_mode":       "per_scene_av_sync_with_subtitles",
            "music_added":     os.path.exists(BG_MUSIC)
        }
