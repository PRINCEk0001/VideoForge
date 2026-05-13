import os
from backend.utils.config_manager import API_CONFIG_FILE

if os.path.exists(API_CONFIG_FILE):
    os.remove(API_CONFIG_FILE)
    print(f"Removed {API_CONFIG_FILE}")
else:
    print("No config file to remove.")
