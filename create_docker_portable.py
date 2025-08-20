#!/usr/bin/env python3
"""
Create portable system from optimized Docker container.
Results in ~200-500MB with all dependencies.
"""

docker_approach = """
# Multi-stage Dockerfile for minimal ComfyUI
FROM python:3.13-slim as builder

# Install only build dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clone ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /opt/comfyui

# Final stage - minimal runtime
FROM python:3.13-slim

# Copy only runtime files
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/comfyui /opt/comfyui

# Set environment
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /opt/comfyui

# Entry point
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
"""

import subprocess
import os

def create_from_docker():
    """Extract minimal system from Docker container."""
    
    # Write Dockerfile
    with open("Dockerfile.minimal", "w") as f:
        f.write(docker_approach)
    
    # Build container
    subprocess.run(["docker", "build", "-f", "Dockerfile.minimal", "-t", "comfyui-minimal", "."])
    
    # Extract filesystem
    subprocess.run(["docker", "create", "--name", "temp-container", "comfyui-minimal"])
    subprocess.run(["docker", "cp", "temp-container:/opt", "./portable-comfyui"])
    subprocess.run(["docker", "rm", "temp-container"])
    
    print("Extracted minimal system from Docker to ./portable-comfyui")

if __name__ == "__main__":
    create_from_docker()
