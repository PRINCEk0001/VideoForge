import httpx
import json
import asyncio

async def monitor_pipeline():
    url = "http://localhost:8001/api/run"
    params = {
        "video_style": "realistic",
        "target_duration_minutes": 1.0,
        "topic_hint": "Modern skyscrapers and smart cities",
        "voice_provider": "edge",
        "target_scene_count": 12
    }
    
    print(f"Triggering pipeline with: {params}")
    
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream("GET", url, params=params) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[len("data: "):]
                        try:
                            data = json.loads(data_str)
                            
                            if "phase" in data:
                                print(f"[Phase {data['phase']}] {data['name']} - {data['status']}", flush=True)
                                if data['status'] == "error":
                                    print(f"!!! Error in Phase {data['phase']}: {data.get('error')}", flush=True)
                            
                            if "event" in data and data["event"] == "pipeline_complete":
                                print("Pipeline Complete!", flush=True)
                                print(json.dumps(data, indent=2), flush=True)
                                break
                            
                            if "event" in data and data["event"] == "pipeline_failed":
                                print(f"Pipeline Failed: {data.get('reason')}", flush=True)
                                break
                                
                        except json.JSONDecodeError:
                            print(f"Raw data: {data_str}", flush=True)
        except Exception as e:
            print(f"Connection error: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(monitor_pipeline())
