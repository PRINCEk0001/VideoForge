import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=key)

print("Available models:")
for m in client.models.list():
    print(f"- {m.name} (Actions: {m.supported_actions})")
