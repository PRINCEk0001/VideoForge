import os
import subprocess

def kill_ffmpeg():
    print("Attempting to kill ffmpeg processes...")
    try:
        # Use taskkill directly via os.system (might be lighter)
        os.system("taskkill /F /IM ffmpeg* /T")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    kill_ffmpeg()
