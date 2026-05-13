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

    def __init__(self):
        keys = ConfigManager.load_api_keys()
        
        self.gemini_key = (
            keys.get("gemini_api")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        
        self.groq_key = (
            keys.get("groq_api")
            or os.getenv("GROQ_API_KEY") 
            or ""
        ).strip()
        
        self.client = None

        if self.gemini_key and self.gemini_key not in PLACEHOLDER_KEYS:
            self.client = genai.Client(api_key=self.gemini_key)

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

        response = self.client.models.generate_content(
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

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.groq_key}"},
                json=payload,
                timeout=45.0,
            )

            # Some models reject response_format; retry once without it.
            if response.status_code == 400:
                payload.pop("response_format", None)
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_key}"},
                    json=payload,
                    timeout=45.0,
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
