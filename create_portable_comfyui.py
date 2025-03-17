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
import time
from typing import List, Optional, Dict, Any, Union

# Constants
ANYMATIX_DIR = "anymatix"
PYTHON_DIR = os.path.join(ANYMATIX_DIR, "python")
COMFYUI_DIR = os.path.join(ANYMATIX_DIR, "ComfyUI")
CUSTOM_NODES_DIR = os.path.join(COMFYUI_DIR, "custom_nodes")
COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
MINIFORGE_BASE_URL = "https://github.com/conda-forge/miniforge/releases/latest/download"


def parse_args() -> argparse.Namespace:
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


def get_version() -> str:
    """Get the version from VERSION.txt."""
    with open("VERSION.txt", "r") as f:
        return f.read().strip()


def get_platform_info() -> tuple[str, str]:
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


def get_miniforge_url() -> str:
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


def run_command(
    cmd: List[str], check: bool = True, shell: bool = False
) -> subprocess.CompletedProcess:
    """Run a command and handle errors."""
    try:
        return subprocess.run(
            cmd,
            check=check,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Error: {e}")
        print(f"Output: {e.stdout if hasattr(e, 'stdout') else ''}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else ''}")
        if check:
            raise
        return e


def create_portable_python() -> None:
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
        # For Windows, use a more robust installation approach
        install_cmd = [miniforge_installer, "/S", "/D=" + os.path.abspath(PYTHON_DIR)]
        run_command(install_cmd)

        # Wait for installation to complete
        print("Waiting for installation to complete...")
        time.sleep(10)
    else:
        run_command([f"./{miniforge_installer}", "-b", "-p", PYTHON_DIR])

    # Clean up installer
    os.remove(miniforge_installer)

    # Install required packages
    print("Installing required packages...")

    if platform.system() == "Windows":
        # On Windows, use a different approach to run conda
        conda_exe = os.path.join(PYTHON_DIR, "Scripts", "conda.exe")
        pip_exe = os.path.join(PYTHON_DIR, "Scripts", "pip.exe")

        # Initialize conda for batch usage
        print("Initializing conda...")
        try:
            run_command([conda_exe, "init", "cmd.exe"], check=False)
        except Exception as e:
            print(f"Warning: Could not initialize conda: {e}")
            print("Continuing with installation...")

        # Install Python 3.10 using conda
        print("Installing Python 3.10...")
        try:
            run_command([conda_exe, "install", "-y", "python=3.10"], check=False)
        except Exception as e:
            print(f"Warning: Could not install Python 3.10 with conda: {e}")
            print("Continuing with installation...")

        # Install requirements using pip directly
        print("Installing requirements with pip...")
        try:
            run_command([pip_exe, "install", "-r", "requirements.txt"], check=False)
        except Exception as e:
            print(f"Warning: Could not install requirements with pip: {e}")
            print("Continuing with installation...")
    else:
        # For Unix-like systems, use the original approach
        conda_exe = os.path.join(PYTHON_DIR, "bin", "conda")
        run_command([conda_exe, "install", "-y", "python=3.10"])

        pip_exe = os.path.join(PYTHON_DIR, "bin", "pip")

        # For macOS with Apple Silicon, optimize NumPy with Accelerate framework
        if platform.system() == "darwin" and platform.machine() == "arm64":
            print("Optimizing for Apple Silicon...")
            # Install NumPy with Accelerate framework
            run_command(
                [
                    conda_exe,
                    "install",
                    "-y",
                    "-c",
                    "conda-forge",
                    "libblas=*=*accelerate",
                ]
            )

            # Pin libblas to use accelerate
            conda_meta_dir = os.path.join(PYTHON_DIR, "conda-meta")
            os.makedirs(conda_meta_dir, exist_ok=True)
            with open(os.path.join(conda_meta_dir, "pinned"), "a") as f:
                f.write("libblas=*=*accelerate\n")

            # Install PyTorch with MPS support
            run_command(
                [pip_exe, "install", "torch>=2.1.0", "torchvision", "torchaudio"]
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
                run_command([pip_exe, "install"] + filtered_requirements)
        else:
            # For other platforms, install all requirements normally
            run_command([pip_exe, "install", "-r", "requirements.txt"])

    # Set executable permissions on files in python/bin directory for Unix-like systems
    if platform.system() != "Windows":
        bin_dir = os.path.join(PYTHON_DIR, "bin")
        print(f"Setting executable permissions on files in {bin_dir}...")

        # Check if bin directory exists
        if os.path.exists(bin_dir):
            # Get all files in the bin directory
            bin_files = [
                os.path.join(bin_dir, f)
                for f in os.listdir(bin_dir)
                if os.path.isfile(os.path.join(bin_dir, f))
            ]

            # Set executable permissions for each file
            for file_path in bin_files:
                try:
                    current_mode = os.stat(file_path).st_mode
                    # Add executable bit for user, group, and others if not already set
                    new_mode = (
                        current_mode | 0o111
                    )  # Add executable bit for user, group, and others
                    os.chmod(file_path, new_mode)
                except Exception as e:
                    print(
                        f"Warning: Could not set executable permission on {file_path}: {e}"
                    )

            print(f"Executable permissions set on {len(bin_files)} files in {bin_dir}")
        else:
            print(f"Warning: Bin directory {bin_dir} does not exist")

    print("Portable Python environment created successfully.")


def clone_comfyui() -> None:
    """Clone the ComfyUI repository."""
    print("Cloning ComfyUI repository...")
    run_command(["git", "clone", COMFYUI_REPO, COMFYUI_DIR])
    print("ComfyUI repository cloned successfully.")


def clone_custom_nodes() -> None:
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
        run_command(["git", "clone", repo_url, repo_dir])

    print("Custom node repositories cloned successfully.")


def create_launch_script() -> None:
    """Create platform-specific launch scripts."""
    print("Creating launch scripts...")
    system, _ = get_platform_info()

    # Create the launch script for macOS
    if system == "darwin":
        launch_script_path = os.path.join(ANYMATIX_DIR, "anymatix_comfyui")

        with open(launch_script_path, "w") as f:
            f.write(
                """#!/bin/bash
# Launch script for ComfyUI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Default port
PORT=${1:-8188}

# Remove quarantine attribute if present (macOS security feature)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Check if quarantine attribute exists before attempting to remove it
    if xattr -l "$SCRIPT_DIR" 2>/dev/null | grep -q "com.apple.quarantine"; then
        echo "Quarantine attribute detected. Removing quarantine attribute from files..."
        xattr -r -d com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "Quarantine attributes removed successfully."
        else
            echo "Warning: Could not remove quarantine attributes. You may need to run this manually:"
            echo "xattr -r -d com.apple.quarantine \\"$SCRIPT_DIR\\""
        fi
    fi
fi

# Change to the ComfyUI directory
cd "$SCRIPT_DIR/ComfyUI"

# Launch ComfyUI with the portable Python using exec to preserve PID
exec "$SCRIPT_DIR/python/bin/python" main.py \\
    --enable-cors-header \\
    "*" \\
    --force-fp16 \\
    --preview-method=none \\
    --port=$PORT
"""
            )

        # Make the launch script executable
        os.chmod(launch_script_path, 0o755)

    # Create the launch script for Linux
    elif system == "linux":
        launch_script_path = os.path.join(ANYMATIX_DIR, "anymatix_comfyui")

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

# Launch ComfyUI with the portable Python using exec to preserve PID
exec "$SCRIPT_DIR/python/bin/python" main.py \\
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
    elif system == "windows":
        launch_script_path = os.path.join(ANYMATIX_DIR, "anymatix_comfyui.bat")

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


def create_zip_package() -> str:
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


def push_to_github(branch: str) -> None:
    """Push changes to GitHub."""
    print(f"Pushing changes to GitHub branch {branch}...")

    # Add all files
    run_command(["git", "add", "."])

    # Commit changes
    run_command(["git", "commit", "-m", "Update portable ComfyUI package"])

    # Push to GitHub
    run_command(["git", "push", "origin", branch])

    print("Changes pushed to GitHub successfully.")


def trigger_github_workflow(workflow: str, branch: str) -> None:
    """Trigger a GitHub workflow."""
    print(f"Triggering GitHub workflow {workflow} on branch {branch}...")

    # Trigger workflow
    run_command(["gh", "workflow", "run", workflow, "--ref", branch])

    print("GitHub workflow triggered successfully.")


def main() -> None:
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
        # Keep the original filename with version and platform info
        # No need to rename to a generic name anymore
        print(f"Using versioned zip file for CI: {zip_filename}")

    # Push to GitHub if requested
    if args.push:
        push_to_github(args.branch)

    # Trigger GitHub workflow if requested
    if args.trigger_workflow:
        trigger_github_workflow(args.workflow, args.branch)

    print("Portable ComfyUI package created successfully.")


if __name__ == "__main__":
    main()
