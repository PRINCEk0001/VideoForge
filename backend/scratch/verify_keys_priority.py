import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.utils.config_manager import ConfigManager

def check_paths():
    print("--- Configuration Path Check ---")
    from backend.utils.config_manager import CONFIG_DIR, API_CONFIG_FILE
    print(f"Config Directory: {CONFIG_DIR}")
    print(f"Config File:      {API_CONFIG_FILE}")
    print(f"Exists:           {os.path.exists(API_CONFIG_FILE)}")
    print("-" * 30)

def simulate_user_keys():
    print("\nSaving dummy user keys for verification...")
    ConfigManager.save_api_keys({
        "gemini_api": "VERIFIED_USER_GEMINI_KEY",
        "elevenlabs_api": "VERIFIED_USER_ELEVEN_KEY"
    })

def check_keys():
    print("\n--- API Key Priority Check ---")
    
    # Reload keys
    keys = ConfigManager.load_api_keys()
    
    providers = ["gemini_api", "groq_api", "pexels_api", "pixabay_api", "elevenlabs_api", "unreal_speech_api"]
    
    for p in providers:
        user_key = keys.get(p)
        env_key = os.getenv(p.upper().replace("_API", "_API_KEY")) or os.getenv("GOOGLE_API_KEY" if p == "gemini_api" else "")
        
        final_key = user_key or env_key
        
        source = "USER (ConfigManager)" if user_key else ("ENV (.env)" if env_key else "NONE")
        
        masked = f"{final_key[:4]}...{final_key[-4:]}" if final_key and len(final_key) > 8 else final_key
        print(f"Provider: {p}")
        print(f"  Source: {source}")
        print(f"  Value:  {masked}")
        print("-" * 30)

if __name__ == "__main__":
    load_dotenv()
    check_paths()
    simulate_user_keys()
    check_keys()
