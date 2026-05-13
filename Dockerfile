# --- Stage 1: Build Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Environment ---
FROM python:3.11-slim

# Install system dependencies (FFmpeg is required for video assembly)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and built frontend
COPY . .
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Create necessary directories for storage
RUN mkdir -p downloads/scenes downloads/audio downloads/synced output downloads/models/hf_cache

# Expose the port (Render will use this if PORT is not set)
EXPOSE 8001

# Command to run the backend (which now also serves the frontend)
# We use the shell form to allow environment variable expansion for PORT
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8001}
