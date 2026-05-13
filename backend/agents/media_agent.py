"""
Phase 5 — Media Agent
Fetches real stock images/videos from Pexels for each scene.
Falls back to Pixabay if Pexels returns no results.
"""
import os
import httpx
import asyncio
import shutil
from backend.agents.base_agent import BaseAgent
from backend.utils.config_manager import ConfigManager
from dotenv import load_dotenv

load_dotenv()

PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PIXABAY_URL = "https://pixabay.com/api/"
PIXABAY_URL = "https://pixabay.com/api/"

import urllib.parse

def _generate_pollinations_image(query: str, video_format: str = "16:9", style: str = "realistic") -> dict:
    """Generate a custom AI image using Pollinations AI (100% Free, No Key)."""
    # Enhancing the prompt for better video-like cinematic quality
    if style == "cartoon":
        style_prompt = "vibrant 3D animated cartoon style, high-end 3D render, Pixar and Disney inspired, cinematic lighting, cute characters, expressive faces, rich textures, 8k resolution, masterpiece"
    else:
        style_prompt = "cinematic, ultra realistic, highly detailed, 8k resolution, photorealistic"
        
    prompt = f"{style_prompt}, {query}"
    encoded = urllib.parse.quote(prompt)
    
    if video_format == "9:16":
        width, height = 1080, 1920
    else:
        width, height = 1920, 1080
        
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
    
    return {
        "url": url,
        "thumbnail": url,
        "type": "image",
        "width": width,
        "height": height,
        "license": "Free AI Generated",
        "attribution": "Generated via Pollinations AI",
        "source": "pollinations_ai",
    }


async def _fetch_pexels_photo(query: str, client: httpx.AsyncClient, video_format: str = "16:9") -> dict | None:
    PEXELS_KEY = ConfigManager.get_api_key("pexels_api") or os.getenv("PEXELS_API_KEY", "")
    if not PEXELS_KEY:
        return None
    try:
        orientation = "portrait" if video_format == "9:16" else "landscape"
        r = await client.get(
            PEXELS_PHOTO_URL,
            headers={"Authorization": PEXELS_KEY},
            params={"query": query, "per_page": 1, "orientation": orientation},
            timeout=10,
        )
        data = r.json()
        photos = data.get("photos", [])
        if photos:
            p = photos[0]
            return {
                "url": p["src"]["large2x"],
                "thumbnail": p["src"]["medium"],
                "type": "image",
                "width": p["width"],
                "height": p["height"],
                "license": "Pexels Free License",
                "attribution": f"Photo by {p['photographer']} on Pexels",
                "source": "pexels",
            }
    except Exception:
        pass
    return None


async def _fetch_pexels_video(query: str, client: httpx.AsyncClient, video_format: str = "16:9") -> dict | None:
    PEXELS_KEY = ConfigManager.get_api_key("pexels_api") or os.getenv("PEXELS_API_KEY", "")
    if not PEXELS_KEY:
        return None
    try:
        orientation = "portrait" if video_format == "9:16" else "landscape"
        r = await client.get(
            PEXELS_VIDEO_URL,
            headers={"Authorization": PEXELS_KEY},
            params={"query": query, "per_page": 3, "orientation": orientation, "size": "large"},
            timeout=10,
        )
        data = r.json()
        videos = data.get("videos", [])
        if videos:
            v = videos[0]
            # Prefer 1080p (1920 width) to avoid massive 4K downloads that slow down the pipeline
            files = v.get("video_files", [])
            # Filter for files that are not larger than 1920 width
            efficient_files = [f for f in files if f.get("width", 0) <= 1920]
            # Sort by width descending within that limit, or fallback to any if none found
            best = sorted(efficient_files or files, key=lambda x: x.get("width", 0), reverse=True)[0]
            
            return {
                "url": best.get("link", ""),
                "thumbnail": v.get("image", ""),
                "type": "video",
                "width": best.get("width", 0),
                "height": best.get("height", 0),
                "duration_seconds": v.get("duration", 0),
                "license": "Pexels Free License",
                "attribution": f"Video by {v['user']['name']} on Pexels",
                "source": "pexels",
            }
    except Exception:
        pass
    return None


async def _fetch_pixabay_photo(query: str, client: httpx.AsyncClient) -> dict | None:
    PIXABAY_KEY = ConfigManager.get_api_key("pixabay_api") or os.getenv("PIXABAY_API_KEY", "")
    if not PIXABAY_KEY:
        return None
    try:
        r = await client.get(
            PIXABAY_URL,
            params={
                "key": PIXABAY_KEY,
                "q": query,
                "image_type": "photo",
                "per_page": 3,
                "safesearch": "true",
            },
            timeout=10,
        )
        hits = r.json().get("hits", [])
        if hits:
            h = hits[0]
            return {
                "url": h["largeImageURL"],
                "thumbnail": h["webformatURL"],
                "type": "image",
                "license": "Pixabay License",
                "attribution": f"Image by {h['user']} on Pixabay",
                "source": "pixabay",
            }
    except Exception:
        pass
    return None


async def _fetch_pixabay_video(query: str, client: httpx.AsyncClient, video_format: str = "16:9") -> dict | None:
    PIXABAY_KEY = ConfigManager.get_api_key("pixabay_api") or os.getenv("PIXABAY_API_KEY", "")
    if not PIXABAY_KEY:
        return None
    try:
        r = await client.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": PIXABAY_KEY,
                "q": query,
                "per_page": 3,
                "safesearch": "true",
            },
            timeout=10,
        )
        hits = r.json().get("hits", [])
        if hits:
            v = hits[0]
            # Pixabay provides several formats, we look for a good quality one
            videos = v.get("videos", {})
            best = videos.get("large") or videos.get("medium") or videos.get("small") or {}
            return {
                "url": best.get("url", ""),
                "thumbnail": f"https://i.vimeocdn.com/video/{v.get('picture_id')}_640x360.jpg",
                "type": "video",
                "width": best.get("width", 0),
                "height": best.get("height", 0),
                "duration_seconds": v.get("duration", 0),
                "license": "Pixabay License",
                "attribution": f"Video by {v['user']} on Pixabay",
                "source": "pixabay",
            }
    except Exception:
        pass
    return None


PLACEHOLDER_MEDIA = {
    "url": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg",
    "thumbnail": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?w=400",
    "type": "image",
    "license": "Pexels Free License",
    "attribution": "Placeholder — add PEXELS_API_KEY to .env for real media",
    "source": "placeholder",
}

PLACEHOLDER_VIDEO = {
    "url": "https://player.vimeo.com/external/370331493.hd.mp4?s=38d513571956244414b06aa15d315024b4f0b2f5&profile_id=172&oauth2_token_id=57447761",
    "thumbnail": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?w=400",
    "type": "video",
    "license": "Pexels Free License",
    "attribution": "Placeholder Video",
    "source": "placeholder",
}


async def _download_file(url: str, dest_path: str, client: httpx.AsyncClient, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            async with client.stream("GET", url, follow_redirects=True, timeout=30) as response:
                if response.status_code == 200:
                    with open(dest_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
                    return dest_path
                else:
                    print(f"[MediaAgent] Download attempt {attempt+1} failed with status {response.status_code}")
        except Exception as e:
            print(f"[MediaAgent] Download attempt {attempt+1} failed: {e}")
        
        if attempt < retries - 1:
            import asyncio
            await asyncio.sleep(1 * (attempt + 1)) # exponential-ish backoff
            
    return None


class MediaAgent(BaseAgent):
    PHASE_NUM = 4
    PHASE_NAME = "Smart Media Selection"

    async def _search_scene_media(self, idx, scene, total_scenes, client, video_format, video_style, media_balance, semaphore, pexels_key, query_cache):
        """Phase 1: Search for metadata without downloading."""
        async with semaphore:
            try:
                keywords = scene.get("keywords", [])
                query = " ".join(keywords) if keywords else scene.get("text", "cinematic")
                
                # Check cache
                if query in query_cache:
                    return {"scene": {**scene, "media": query_cache[query]}, "media_info": {"scene_id": idx, **query_cache[query]}}

                scene_ratio = (idx - 1) / max(1, total_scenes - 1) if total_scenes > 1 else 0.5
                use_stock = media_balance > scene_ratio

                candidates = []
                # 1. ALWAYS Try Video First (Pexels -> Pixabay)
                is_realistic = video_style.lower() == "realistic"
                
                if pexels_key:
                    vid = await _fetch_pexels_video(query, client, video_format)
                    if vid: candidates.append(vid)
                
                if not candidates:
                    vid = await _fetch_pixabay_video(query, client, video_format)
                    if vid: candidates.append(vid)

                # 2. If no video found, try images/AI ONLY IF style is NOT realistic
                if not candidates:
                    if is_realistic:
                        # Force another video search with a generic query
                        generic_query = "cinematic nature background"
                        vid = await _fetch_pexels_video(generic_query, client, video_format)
                        if vid: 
                            candidates.append(vid)
                        else:
                            candidates.append({**PLACEHOLDER_VIDEO, "score": 0.5})
                    else:
                        # Non-realistic: Use AI Images or Stock Photos
                        ai_media = _generate_pollinations_image(query, video_format, video_style)
                        candidates.append({
                            **ai_media,
                            "description": f"AI Creative: {query}",
                            "source": "ai",
                            "quality": 0.8,
                            "motion": 0.2,
                            "clarity": 0.9
                        })
                
                # 3. Final Fallback (Placeholder)
                if not candidates:
                    fallback = PLACEHOLDER_VIDEO if is_realistic else PLACEHOLDER_MEDIA
                    candidates.append({**fallback, "quality": 0.5, "motion": 0, "clarity": 0.5})

                # Select best candidate
                best_media = candidates[0]
                if is_realistic and best_media.get("type") != "video":
                    best_media = {**PLACEHOLDER_VIDEO, "score": 0.1}

                best_media["query"] = query
                query_cache[query] = best_media # Cache the metadata
                
                return {
                    "scene": {**scene, "media": best_media},
                    "media_info": {
                        "scene_id": idx,
                        "score": round(best_media.get("score", 0.9), 2),
                        "source": best_media.get("source"),
                        "url": best_media.get("url"),
                        "type": best_media.get("type")
                    }
                }
            except Exception as e:
                print(f"[MediaAgent] Scene {idx} failed: {e}")
                # Fallback to placeholder to prevent crashing the whole gather
                fallback = PLACEHOLDER_VIDEO if video_style.lower() == "realistic" else PLACEHOLDER_MEDIA
                placeholder = {**fallback, "local_path": None}
                return {
                    "scene": {**scene, "media": placeholder},
                    "media_info": {
                        "scene_id": idx,
                        "score": 0.0,
                        "source": "error",
                        "local_path": None
                    }
                }

    async def run(self, pipeline_json: dict) -> dict:
        scenes = pipeline_json.get("scenes", [])
        video_format = pipeline_json.get("video_format", "16:9")
        video_style = pipeline_json.get("video_style", "realistic")
        media_balance = float(pipeline_json.get("media_balance", 0.5))
        
        if video_style == "cartoon":
            media_balance = 0.0
        
        # Pre-load Pexels Key to avoid concurrent file read issues
        pexels_key = ConfigManager.get_api_key("pexels_api") or os.getenv("PEXELS_API_KEY", "")

        # Use a smaller semaphore for API searches
        search_semaphore = asyncio.Semaphore(3 if video_style == "realistic" else 5)
        # Use a larger semaphore for actual downloads
        download_semaphore = asyncio.Semaphore(10 if video_style == "realistic" else 15)
        
        query_cache = {}
        
        async with httpx.AsyncClient() as client:
            # STEP 1: Search for all media in parallel (bounded by search_semaphore)
            search_tasks = []
            for idx, scene in enumerate(scenes, 1):
                search_tasks.append(self._search_scene_media(idx, scene, len(scenes), client, video_format, video_style, media_balance, search_semaphore, pexels_key, query_cache))
            
            search_results = await asyncio.gather(*search_tasks)
            
            # STEP 2: Download all media in parallel (bounded by download_semaphore)
            async def _download_wrapper(res):
                info = res["media_info"]
                url = info.get("url")
                if not url: return res
                
                is_real = video_style.lower() == "realistic"
                ext = ".mp4" if is_real or info.get("type") == "video" else ".jpg"
                local_path = f"downloads/scenes/scene_{info['scene_id']}{ext}"
                
                async with download_semaphore:
                    try:
                        saved_path = await _download_file(url, local_path, client)
                        res["scene"]["media"]["local_path"] = saved_path
                        res["media_info"]["local_path"] = saved_path
                    except Exception as de:
                        print(f"[MediaAgent] Download error for scene {info['scene_id']}: {de}")
                        res["scene"]["media"]["local_path"] = None
                        res["media_info"]["local_path"] = None
                return res

            print(f"[MediaAgent] Starting parallel download of {len(search_results)} scenes...")
            results = await asyncio.gather(*[_download_wrapper(r) for r in search_results])
            print(f"[MediaAgent] Parallel download completed.")

        # Reconstruct in order
        enriched_scenes = [r["scene"] for r in results]
        media_list = [r["media_info"] for r in results]

        # Final check: Fallback for failed downloads (use unique generic videos instead of repetition)
        FALLBACK_POOL = [
            "https://player.vimeo.com/external/370331493.hd.mp4?s=38d513571956244414b06aa15d315024b4f0b2f5&profile_id=172&oauth2_token_id=57447761",
            "https://player.vimeo.com/external/494444583.hd.mp4?s=38d513571956244414b06aa15d315024b4f0b2f5&profile_id=172&oauth2_token_id=57447761",
            "https://player.vimeo.com/external/368363747.hd.mp4?s=38d513571956244414b06aa15d315024b4f0b2f5&profile_id=172&oauth2_token_id=57447761"
        ]
        
        for i in range(len(media_list)):
            if not media_list[i].get("local_path"):
                # Use a different fallback from the pool based on index to avoid repetition
                fallback_url = FALLBACK_POOL[i % len(FALLBACK_POOL)]
                is_real = video_style.lower() == "realistic"
                ext = ".mp4" if is_real else ".jpg"
                local_path = f"downloads/scenes/scene_{i+1}{ext}"
                
                # Try downloading this unique fallback
                async with httpx.AsyncClient() as client:
                    saved_path = await _download_file(fallback_url, local_path, client)
                    if saved_path:
                        media_list[i]["local_path"] = saved_path
                        enriched_scenes[i]["media"]["local_path"] = saved_path
                    elif i > 0:
                        # Absolute last resort: reuse previous
                        prev_path = media_list[i-1].get("local_path")
                        if prev_path:
                            try:
                                shutil.copy2(prev_path, local_path)
                                media_list[i]["local_path"] = local_path
                                enriched_scenes[i]["media"]["local_path"] = local_path
                            except: pass

        return {
            "scenes": enriched_scenes,
            "media": media_list
        }
