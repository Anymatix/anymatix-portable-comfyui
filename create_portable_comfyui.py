#!/usr/bin/env python3
"""
Script to create a portable ComfyUI package.
This script will:
1. Create a portable Python environment
2. Clone the ComfyUI repository
3. Clone the custom node repositories
4. Create a launch script
5. Package everything into a zip file
"""

import os
import json
import subprocess
import platform
import argparse
import urllib.request
import zipfile

# Constants
ANYMATIX_DIR = "anymatix"
PYTHON_DIR = os.path.join(ANYMATIX_DIR, "python")
COMFYUI_DIR = os.path.join(ANYMATIX_DIR, "ComfyUI")
CUSTOM_NODES_DIR = os.path.join(COMFYUI_DIR, "custom_nodes")
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
MINIFORGE_BASE_URL = "https://github.com/conda-forge/miniforge/releases/latest/download"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Create a portable ComfyUI package")
    parser.add_argument(
        "--local", action="store_true", help="Create the package locally"
    )
    parser.add_argument("--ci", action="store_true", help="Create the package on CI")
    return parser.parse_args()


def get_miniforge_url():
    """Get the URL for the Miniforge installer based on the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine == "x86_64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-MacOSX-x86_64.sh"
        elif machine == "arm64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-MacOSX-arm64.sh"
    elif system == "linux":
        if machine == "x86_64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-Linux-x86_64.sh"
        elif machine == "aarch64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-Linux-aarch64.sh"
    elif system == "windows":
        if machine == "amd64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-Windows-x86_64.exe"

    raise ValueError(f"Unsupported platform: {system} {machine}")


def create_portable_python():
    """Create a portable Python environment using Miniforge."""
    print("Creating portable Python environment...")

    # Download Miniforge installer
    miniforge_url = get_miniforge_url()
    miniforge_installer = os.path.basename(miniforge_url)

    print(f"Downloading Miniforge from {miniforge_url}...")
    urllib.request.urlretrieve(miniforge_url, miniforge_installer)

    # Make the installer executable on Unix-like systems
    if platform.system() != "Windows":
        os.chmod(miniforge_installer, 0o755)

    # Install Miniforge
    print("Installing Miniforge...")
    if platform.system() == "Windows":
        subprocess.run(
            [miniforge_installer, "/S", "/D=" + os.path.abspath(PYTHON_DIR)], check=True
        )
    else:
        subprocess.run([f"./{miniforge_installer}", "-b", "-p", PYTHON_DIR], check=True)

    # Clean up installer
    os.remove(miniforge_installer)

    # Install required packages
    print("Installing required packages...")
    conda_exe = os.path.join(PYTHON_DIR, "bin", "conda")
    if platform.system() == "Windows":
        conda_exe = os.path.join(PYTHON_DIR, "Scripts", "conda.exe")

    # Create a new environment in the portable Python
    subprocess.run([conda_exe, "install", "-y", "python=3.10"], check=True)

    # Install pip packages from requirements.txt
    pip_exe = os.path.join(PYTHON_DIR, "bin", "pip")
    if platform.system() == "Windows":
        pip_exe = os.path.join(PYTHON_DIR, "Scripts", "pip.exe")

    subprocess.run([pip_exe, "install", "-r", "requirements.txt"], check=True)

    print("Portable Python environment created successfully.")


def clone_comfyui():
    """Clone the ComfyUI repository."""
    print("Cloning ComfyUI repository...")
    subprocess.run(["git", "clone", COMFYUI_REPO, COMFYUI_DIR], check=True)
    print("ComfyUI repository cloned successfully.")


def clone_custom_nodes():
    """Clone the custom node repositories."""
    print("Cloning custom node repositories...")

    # Create custom_nodes directory if it doesn't exist
    os.makedirs(CUSTOM_NODES_DIR, exist_ok=True)

    # Read repos.json
    with open("repos.json", "r") as f:
        repos = json.load(f)

    # Clone each repository
    for repo in repos:
        repo_url = repo["url"]
        repo_name = os.path.basename(repo_url).replace(".git", "")
        repo_dir = os.path.join(CUSTOM_NODES_DIR, repo_name)

        print(f"Cloning {repo_url}...")
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True)

    print("Custom node repositories cloned successfully.")


def create_launch_script():
    """Create the launch script."""
    print("Creating launch script...")

    # Create the launch script for macOS
    launch_script_path = os.path.join(ANYMATIX_DIR, "anymatix_comfyui_macos")

    with open(launch_script_path, "w") as f:
        f.write(
            """#!/bin/bash
# Launch script for ComfyUI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Default port
PORT=${1:-8188}

# Change to the ComfyUI directory
cd "$SCRIPT_DIR/ComfyUI"

# Launch ComfyUI with the portable Python
"$SCRIPT_DIR/python/bin/python" main.py \\
    --enable-cors-header \\
    "*" \\
    --force-fp16 \\
    --preview-method=none \\
    --port=$PORT
"""
        )

    # Make the launch script executable
    os.chmod(launch_script_path, 0o755)

    print("Launch script created successfully.")


def create_zip_package():
    """Create a zip package of the portable ComfyUI."""
    print("Creating zip package...")

    zip_filename = "anymatix-portable-comfyui.zip"

    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(ANYMATIX_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(ANYMATIX_DIR))
                zipf.write(file_path, arcname)

    print(f"Zip package created successfully: {zip_filename}")


def main():
    """Main function."""
    # Parse arguments but we don't need to use them for now
    parse_args()

    # Create anymatix directory
    os.makedirs(ANYMATIX_DIR, exist_ok=True)

    # Create portable Python environment
    create_portable_python()

    # Clone ComfyUI repository
    clone_comfyui()

    # Clone custom node repositories
    clone_custom_nodes()

    # Create launch script
    create_launch_script()

    # Create zip package
    create_zip_package()

    print("Portable ComfyUI package created successfully.")


if __name__ == "__main__":
    main()
