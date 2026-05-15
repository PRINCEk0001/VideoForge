from huggingface_hub import HfApi

def deploy():
    api = HfApi()
    repo_id = "kkoriprince90/VideoForge-AI"
    
    ignore = [
        "**/node_modules/**",
        "**/__pycache__/**",
        "downloads/**",
        "output/**",
        ".git/**",
        ".env",
        "*.mp4",
        "*.mp3",
        "*.wav",
        ".venv/**",
        "env/**",
        "frontend/dist/**"
    ]
    
    print(f"Uploading to {repo_id}...")
    api.upload_folder(
        folder_path=".",
        repo_id=repo_id,
        repo_type="space",
        ignore_patterns=ignore,
        commit_message="Fix: Restore missing FRONTEND_DIST variable"
    )
    print("Done!")

if __name__ == "__main__":
    deploy()
