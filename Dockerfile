# Production Dockerfile for VideoForge AI
# This handles FFmpeg installation and the Python multi-agent backend.

FROM python:3.11-slim

# Install system dependencies (FFmpeg is required for video assembly)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories for storage
RUN mkdir -p downloads/scenes downloads/audio downloads/synced output

# Expose the backend port
EXPOSE 8001

# Command to run the backend
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
