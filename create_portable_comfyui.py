#!/usr/bin/env python3
"""
Script to create a portable ComfyUI package.
This script will:
1. Create a portable Python environment
2. Clone the ComfyUI repository
3. Clone the custom node repositories
4. Create a launch script (platform-specific)
5. Package everything into a zip file
6. Optionally push changes to GitHub and trigger workflows
"""

import os
import json
import subprocess
import platform
import argparse
import urllib.request
import zipfile
import sys
import shutil

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
    parser.add_argument("--push", action="store_true", help="Push changes to GitHub")
    parser.add_argument(
        "--trigger-workflow", action="store_true", help="Trigger GitHub workflow"
    )
    parser.add_argument("--workflow", default="build.yml", help="Workflow file name")
    parser.add_argument("--branch", default="main", help="Branch to push to")
    return parser.parse_args()


def get_version():
    """Get the version from VERSION.txt."""
    with open("VERSION.txt", "r") as f:
        return f.read().strip()


def get_platform_info():
    """Get platform information."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Map machine architecture to a more user-friendly name
    arch_map = {
        "x86_64": "x64",
        "amd64": "x64",
        "i386": "x86",
        "i686": "x86",
        "arm64": "arm64",
        "aarch64": "arm64",
    }

    arch = arch_map.get(machine, machine)

    return system, arch


def get_miniforge_url():
    """Get the URL for the Miniforge installer based on the current platform."""
    system, machine = get_platform_info()

    if system == "darwin":
        if machine == "x64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-MacOSX-x86_64.sh"
        elif machine == "arm64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-MacOSX-arm64.sh"
    elif system == "linux":
        if machine == "x64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-Linux-x86_64.sh"
        elif machine == "arm64":
            return f"{MINIFORGE_BASE_URL}/Miniforge3-Linux-aarch64.sh"
    elif system == "windows":
        if machine == "x64":
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

    # For macOS with Apple Silicon, optimize NumPy with Accelerate framework
    if platform.system() == "darwin" and platform.machine() == "arm64":
        print("Optimizing for Apple Silicon...")
        # Install NumPy with Accelerate framework
        subprocess.run(
            [conda_exe, "install", "-y", "-c", "conda-forge", "libblas=*=*accelerate"],
            check=True,
        )
        # Pin libblas to use accelerate
        conda_meta_dir = os.path.join(PYTHON_DIR, "conda-meta")
        os.makedirs(conda_meta_dir, exist_ok=True)
        with open(os.path.join(conda_meta_dir, "pinned"), "a") as f:
            f.write("libblas=*=*accelerate\n")

        # Install PyTorch with MPS support
        subprocess.run(
            [pip_exe, "install", "torch>=2.1.0", "torchvision", "torchaudio"],
            check=True,
        )

        # Install other requirements
        with open("requirements.txt", "r") as f:
            requirements = f.read().splitlines()

        # Filter out torch, torchvision, torchaudio as they're already installed
        filtered_requirements = [
            req
            for req in requirements
            if not req.startswith(("torch", "torchvision", "torchaudio", "#"))
        ]

        if filtered_requirements:
            subprocess.run([pip_exe, "install"] + filtered_requirements, check=True)
    else:
        # For other platforms, install all requirements normally
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
    """Create platform-specific launch scripts."""
    print("Creating launch scripts...")
    system, _ = get_platform_info()

    # Create the launch script for macOS
    if system == "darwin" or system == "linux":
        launch_script_path = os.path.join(ANYMATIX_DIR, f"anymatix_comfyui_{system}")

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

    # Create the launch script for Windows
    if system == "windows":
        launch_script_path = os.path.join(ANYMATIX_DIR, "anymatix_comfyui_windows.bat")

        with open(launch_script_path, "w") as f:
            f.write(
                """@echo off
REM Launch script for ComfyUI

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0

REM Default port
if "%1"=="" (
    set PORT=8188
) else (
    set PORT=%1
)

REM Change to the ComfyUI directory
cd "%SCRIPT_DIR%ComfyUI"

REM Launch ComfyUI with the portable Python
"%SCRIPT_DIR%python\\python.exe" main.py ^
    --enable-cors-header ^
    "*" ^
    --force-fp16 ^
    --preview-method=none ^
    --port=%PORT%
"""
            )

    print("Launch scripts created successfully.")


def create_zip_package():
    """Create a zip package of the portable ComfyUI."""
    print("Creating zip package...")

    # Get version and platform info
    version = get_version()
    system, arch = get_platform_info()

    # Create zip filename with version and architecture
    zip_filename = f"anymatix-portable-comfyui-{system}-{arch}-v{version}.zip"

    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(ANYMATIX_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(ANYMATIX_DIR))
                try:
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname)
                    else:
                        print(f"Warning: File not found, skipping: {file_path}")
                except Exception as e:
                    print(f"Warning: Error adding file to zip: {file_path}, Error: {e}")

    print(f"Zip package created successfully: {zip_filename}")
    return zip_filename


def push_to_github(branch):
    """Push changes to GitHub."""
    print(f"Pushing changes to GitHub branch {branch}...")

    # Add all files
    subprocess.run(["git", "add", "."], check=True)

    # Commit changes
    subprocess.run(
        ["git", "commit", "-m", "Update portable ComfyUI package"], check=True
    )

    # Push to GitHub
    subprocess.run(["git", "push", "origin", branch], check=True)

    print("Changes pushed to GitHub successfully.")


def trigger_github_workflow(workflow, branch):
    """Trigger a GitHub workflow."""
    print(f"Triggering GitHub workflow {workflow} on branch {branch}...")

    # Trigger workflow
    subprocess.run(["gh", "workflow", "run", workflow, "--ref", branch], check=True)

    print("GitHub workflow triggered successfully.")


def main():
    """Main function."""
    args = parse_args()

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
    zip_filename = create_zip_package()

    # If we're on CI, rename the zip file to a standard name for the artifact
    if args.ci:
        system, arch = get_platform_info()
        standard_name = f"anymatix-portable-comfyui.zip"
        shutil.copy(zip_filename, standard_name)
        print(f"Created standardized zip file for CI: {standard_name}")

    # Push to GitHub if requested
    if args.push:
        push_to_github(args.branch)

    # Trigger GitHub workflow if requested
    if args.trigger_workflow:
        trigger_github_workflow(args.workflow, args.branch)

    print("Portable ComfyUI package created successfully.")


if __name__ == "__main__":
    main()
