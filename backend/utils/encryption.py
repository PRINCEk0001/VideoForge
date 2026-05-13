import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

load_dotenv()

class EncryptionManager:
    _fernet = None

    @classmethod
    def _get_fernet(cls):
        if cls._fernet is None:
            # Use a master secret from .env, or a default one (less secure but functional)
            secret = os.getenv("ENCRYPTION_MASTER_KEY", "videoforge-default-secret-key-2026")
            salt = b'videoforge_salt_123' # Fixed salt for consistency across restarts
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
            cls._fernet = Fernet(key)
        return cls._fernet

    @classmethod
    def encrypt(cls, data: str) -> str:
        if not data:
            return ""
        f = cls._get_fernet()
        return f.encrypt(data.encode()).decode()

    @classmethod
    def decrypt(cls, encrypted_data: str) -> str:
        if not encrypted_data:
            return ""
        try:
            f = cls._get_fernet()
            return f.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return "" # Return empty if decryption fails (e.g. key changed)

# Compatibility aliases
def encrypt_value(data: str) -> str:
    return EncryptionManager.encrypt(data)

def decrypt_value(data: str) -> str:
    return EncryptionManager.decrypt(data)
