"""
Base Agent — abstract class for all pipeline agents.
Every agent must implement PHASE_NUM, PHASE_NAME, and run().
Uses the google-genai SDK (google-genai>=1.0).
"""
import os
import json
import re
from abc import ABC, abstractmethod

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.utils.config_manager import ConfigManager

load_dotenv()

MODEL = "gemini-2.0-flash-lite"
GROQ_MODELS = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
PLACEHOLDER_KEYS = {"", "your_gemini_api_key_here", "your_groq_api_key_here"}


class BaseAgent(ABC):
    PHASE_NUM: int = 0
    PHASE_NAME: str = "Base"

    def __init__(self, request_keys: dict = None):
        config_keys = ConfigManager.load_api_keys()
        request_keys = request_keys or {}
        
        # Helper to get key with priority: Request -> Config -> Env
        def get_key(request_name, config_name, env_name):
            return (request_keys.get(request_name) or config_keys.get(config_name) or os.getenv(env_name) or "").strip()

        self.gemini_key = get_key("gemini_api", "gemini_api", "GEMINI_API_KEY")
        if not self.gemini_key:
            self.gemini_key = os.getenv("GOOGLE_API_KEY", "").strip()

        self.groq_key = get_key("groq_api", "groq_api", "GROQ_API_KEY")
        self.pexels_key = get_key("pexels_api", "pexels_api", "PEXELS_API_KEY")
        self.pixabay_key = get_key("pixabay_api", "pixabay_api", "PIXABAY_API_KEY")
        self.elevenlabs_key = get_key("elevenlabs_api", "elevenlabs_api", "ELEVENLABS_API_KEY")
        self.unreal_key = get_key("unreal_speech_api", "unreal_speech_api", "UNREAL_SPEECH_API_KEY")
        
        self.client = None

        if self.gemini_key and self.gemini_key not in PLACEHOLDER_KEYS:
            # Use AsyncClient for better performance in FastAPI
            self.client = genai.Client(api_key=self.gemini_key, http_options={'api_version': 'v1alpha'})

    def _extract_json_text(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if not text:
            raise ValueError("Empty LLM response")

        # Strip markdown fences if provider ignores JSON mode.
        text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.IGNORECASE)
        text = text.strip()

        if text.startswith("{") and text.endswith("}"):
            return text

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response")
        return text[start:end + 1]

    def _parse_json_response(self, raw_text: str) -> dict:
        parsed = json.loads(self._extract_json_text(raw_text))
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object")
        return parsed

    async def _attempt_gemini(self, full_prompt: str) -> dict:
        if not self.client:
            raise RuntimeError("Gemini key/client not available")

        response = await self.client.aio.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        return self._parse_json_response(response.text or "")

    async def _attempt_groq(self, full_prompt: str, model_name: str) -> dict:
        if not self.groq_key or self.groq_key in PLACEHOLDER_KEYS:
            raise RuntimeError("Groq key not available")

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": full_prompt}],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.groq_key}"},
                json=payload,
            )

            # Some models reject response_format; retry once without it.
            if response.status_code == 400:
                payload.pop("response_format", None)
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_key}"},
                    json=payload,
                )

            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._parse_json_response(content)

    async def call_llm(self, prompt: str) -> dict:
        """
        Call LLM providers with fallback:
        Gemini -> Groq Llama3 -> Groq Mixtral.
        Includes 429 retry logic.
        """
        system_instruction = "Return ONLY a valid JSON object for the requested task. Do not include markdown fences or any other text."
        full_prompt = f"{system_instruction}\n\nTask:\n{prompt}"
        attempt_errors = []

        providers = [("GEMINI", MODEL)] + [("GROQ", m) for m in GROQ_MODELS]
        
        for provider, model_name in providers:
            for retry_attempt in range(3):
                try:
                    if provider == "GEMINI":
                        data = await self._attempt_gemini(full_prompt)
                    else:
                        data = await self._attempt_groq(full_prompt, model_name)
                    if data:
                        return data
                    raise ValueError("Provider returned empty JSON object")
                except Exception as exc:
                    err_msg = str(exc)
                    
                    # Enhanced error reporting for common API issues
                    if "401" in err_msg or "403" in err_msg or "authentication" in err_msg.lower():
                        err_msg = f"API Key Invalid or Expired. Please check your {provider} key in Settings."
                    elif "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        wait_time = (retry_attempt + 1) * 5
                        print(f"[{self.PHASE_NAME}] 429 Rate Limit hit for {provider}. Retrying in {wait_time}s...")
                        import asyncio
                        await asyncio.sleep(wait_time)
                        continue
                    
                    err = {
                        "provider": provider,
                        "model": model_name,
                        "error": err_msg,
                    }
                    attempt_errors.append(err)
                    print(
                        f"[{self.PHASE_NAME}] {provider} ({model_name}) failed: {err_msg}"
                    )
                    break # Move to next provider

        raise RuntimeError(
            f"[{self.PHASE_NAME}] All LLM APIs failed after regeneration: "
            f"{json.dumps(attempt_errors[-6:])}"
        )

    @abstractmethod
    async def run(self, pipeline_json: dict) -> dict:
        """Run this agent and return enriched dict to merge into pipeline."""
        ...
