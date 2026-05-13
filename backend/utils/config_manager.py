import os
import json
from backend.utils.encryption import encrypt_value, decrypt_value

# Use absolute paths relative to the project root for better reliability in deployment
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
CONFIG_DIR = os.path.join(BASE_DIR, "configs")
API_CONFIG_FILE = os.path.join(CONFIG_DIR, "api_config.encrypted")
PREFS_FILE = os.path.join(CONFIG_DIR, "user_preferences.json")


class ConfigManager:
    @staticmethod
    def _ensure_dir():
        os.makedirs(CONFIG_DIR, exist_ok=True)

    # --- API Keys (Encrypted) ---
    @staticmethod
    def load_api_keys() -> dict:
        """Load and decrypt API keys."""
        ConfigManager._ensure_dir()
        if not os.path.exists(API_CONFIG_FILE):
            return {}
        
        try:
            with open(API_CONFIG_FILE, "r", encoding="utf-8") as f:
                encrypted_data = json.load(f)
            
            decrypted_data = {}
            for key, value in encrypted_data.items():
                decrypted_data[key] = decrypt_value(value)
            return decrypted_data
        except Exception as e:
            print(f"[ConfigManager] Error loading API keys: {e}")
            return {}

    @staticmethod
    def save_api_keys(keys: dict):
        """Encrypt and save API keys."""
        ConfigManager._ensure_dir()
        
        # Load existing first to merge
        existing = ConfigManager.load_api_keys()
        existing.update(keys)
        
        encrypted_data = {}
        for k, v in existing.items():
            if v:  # Only save non-empty keys
                encrypted_data[k] = encrypt_value(v)
                
        with open(API_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(encrypted_data, f, indent=2)

    @staticmethod
    def get_api_key(provider: str) -> str:
        """Helper to get a specific decrypted key."""
        keys = ConfigManager.load_api_keys()
        return keys.get(provider, "")

    @staticmethod
    def get_masked_keys() -> dict:
        """Return keys masked for UI display."""
        keys = ConfigManager.load_api_keys()
        masked = {}
        for k, v in keys.items():
            if v:
                masked[k] = f"{v[:4]}...{v[-4:]}" if len(v) > 8 else "***"
            else:
                masked[k] = ""
        return masked

    # --- User Preferences (Plaintext JSON) ---
    @staticmethod
    def load_preferences() -> dict:
        ConfigManager._ensure_dir()
        if not os.path.exists(PREFS_FILE):
            return {}
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def save_preferences(prefs: dict):
        ConfigManager._ensure_dir()
        existing = ConfigManager.load_preferences()
        existing.update(prefs)
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
