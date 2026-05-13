import os
import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_KEY = os.getenv("PEXELS_API_KEY")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY")

def fast_download():
    print("Starting fast test download...")
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    # 1. Download Video
    print("\n--- 1. Fetching Video ---")
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_KEY}
    params = {"query": "AI tools", "per_page": 1}
    
    r = requests.get(url, headers=headers, params=params)
    data = r.json()
    
    videos = data.get("videos", [])
    if videos:
        v = videos[0]
        files = sorted(v.get("video_files", []), key=lambda x: x.get("width", 0), reverse=True)
        if files:
            best_link = files[0]["link"]
            video_filename = "downloads/fast_test_video.mp4"
            print(f"Downloading video to {video_filename}...")
            
            dl_r = requests.get(best_link, stream=True)
            with open(video_filename, 'wb') as f:
                for chunk in dl_r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Video downloaded successfully!")
        else:
            print("No video files found.")
    else:
        print("No videos found on Pexels.")

    # 2. Download Audio
    print("\n--- 2. Fetching Audio (ElevenLabs) ---")
    if ELEVENLABS_KEY:
        voice_id = "pNInz6obpgDQGcFmaJgB" # Adam
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        tts_headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_KEY
        }
        tts_data = {
            "text": "Hello! This is a quick test of the AI video maker. Here is your video with generated audio.",
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
        print("Generating voiceover...")
        try:
            tts_r = requests.post(tts_url, json=tts_data, headers=tts_headers)
            if tts_r.status_code == 200:
                audio_filename = "downloads/fast_test_audio.mp3"
                with open(audio_filename, 'wb') as f:
                    f.write(tts_r.content)
                print(f"Audio downloaded successfully to {audio_filename}!")
                print("\nSuccess! You now have both the video and the audio in the 'downloads' folder.")
            else:
                print(f"ElevenLabs error: {tts_r.status_code} - {tts_r.text}")
        except Exception as e:
            print("Failed to get audio:", e)
    else:
        print("ELEVENLABS_API_KEY not found in .env file.")

if __name__ == "__main__":
    fast_download()
