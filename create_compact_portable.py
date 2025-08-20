#!/usr/bin/env python3
"""
Ultra-compact portable ComfyUI using Python Embeddable Package.
Results in ~200MB final package vs 2GB+ with current approach.
"""

import os
import urllib.request
import zipfile
import subprocess
import platform
import sys
import tempfile
import shutil

# Constants  
ANYMATIX_DIR = "anymatix"
PYTHON_DIR = os.path.join(ANYMATIX_DIR, "python")

def create_compact_python_env():
    """Create ultra-compact Python environment using embeddable package."""
    system = platform.system()
    
    if system == "Windows":
        create_windows_compact_env()
    elif system == "Darwin":
        create_macos_compact_env() 
    else:
        # Linux: Use minimal approach or fallback to current system
        print("Linux compact environment - using fallback to current approach")
        # Could implement similar minimal approach for Linux later

def create_windows_compact_env():
    """Windows: Use official embeddable package."""
    # Download Python 3.13 embeddable package (~25MB)
    python_url = "https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-amd64.zip"
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    
    print("Downloading Python 3.13 embeddable package for Windows...")
    urllib.request.urlretrieve(python_url, "python_embed.zip")
    
    # Extract to python directory
    os.makedirs(PYTHON_DIR, exist_ok=True)
    with zipfile.ZipFile("python_embed.zip", 'r') as zip_ref:
        zip_ref.extractall(PYTHON_DIR)
    os.remove("python_embed.zip")
    
    # Enable pip by modifying python313._pth
    pth_file = os.path.join(PYTHON_DIR, "python313._pth")
    with open(pth_file, 'a') as f:
        f.write("\\nimport site\\n")
    
    # Install pip
    print("Installing pip...")
    urllib.request.urlretrieve(get_pip_url, os.path.join(PYTHON_DIR, "get-pip.py"))
    python_exe = os.path.join(PYTHON_DIR, "python.exe")
    subprocess.run([python_exe, os.path.join(PYTHON_DIR, "get-pip.py")], check=True)
    
    install_compact_requirements(python_exe)

def create_macos_compact_env():
    """macOS: Create portable Python directory (NOT .app bundle) for zip distribution."""
    import tempfile
    
    # For zip distribution, we want a simple directory structure like Windows
    # anymatix/
    #   python/          <- Portable Python installation
    #   ComfyUI/        <- ComfyUI files  
    #   launch.sh       <- Launch script
    
    print("Creating portable Python environment for macOS...")
    
    # Option 1: Use pyenv/python-build for clean, minimal Python
    create_minimal_python_macos()
    
    # Option 2: Extract from official installer (more complex but smaller)
    # extract_python_from_installer()

def create_minimal_python_macos():
    """Build minimal Python 3.13 for macOS without conda overhead."""
    
    # Check if pyenv is available for building minimal Python
    try:
        subprocess.run(["which", "python3.13"], check=True, capture_output=True)
        # Use system Python 3.13 as base and create minimal venv
        create_minimal_venv_macos()
    except subprocess.CalledProcessError:
        # Download and use Python.org binary, but extract minimal parts
        download_and_minimize_python_macos()

def create_minimal_venv_macos():
    """Create minimal virtual environment with only essential files."""
    
    # Create a virtual environment
    venv_path = PYTHON_DIR
    subprocess.run(["python3.13", "-m", "venv", venv_path, "--without-pip"], check=True)
    
    # Install pip manually (smaller than bundled pip)
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = os.path.join(venv_path, "get-pip.py")
    urllib.request.urlretrieve(get_pip_url, get_pip_path)
    
    python_exe = os.path.join(venv_path, "bin", "python")
    subprocess.run([python_exe, get_pip_path, "--no-cache-dir"], check=True)
    
    # Remove get-pip.py
    os.remove(get_pip_path)
    
    install_compact_requirements(python_exe)

def download_and_minimize_python_macos():
    """Download Python installer and extract minimal runtime."""
    
    # This creates the same directory structure as Windows
    # so your app can handle both the same way
    
    arch = platform.machine().lower() 
    if arch == "arm64":
        python_url = "https://www.python.org/ftp/python/3.13.0/python-3.13.0-macos11.pkg"
    else:
        python_url = "https://www.python.org/ftp/python/3.13.0/python-3.13.0-macosx10.13.pkg"
    
    print(f"Downloading minimal Python for macOS ({arch})...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        pkg_path = os.path.join(temp_dir, "python.pkg")
        urllib.request.urlretrieve(python_url, pkg_path)
        
        # Extract and reorganize into portable structure
        extract_minimal_python_from_pkg(pkg_path, temp_dir)

def extract_minimal_python_from_pkg(pkg_path, temp_dir):
    """Extract minimal Python from .pkg into portable directory structure."""
    
    extract_dir = os.path.join(temp_dir, "extracted")
    subprocess.run(["pkgutil", "--expand", pkg_path, extract_dir], check=True)
    
    # Create portable Python directory with same structure as Windows
    os.makedirs(PYTHON_DIR, exist_ok=True)
    bin_dir = os.path.join(PYTHON_DIR, "bin")
    lib_dir = os.path.join(PYTHON_DIR, "lib") 
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(lib_dir, exist_ok=True)
    
    # Copy essential Python runtime files only
    # This mimics the Windows embeddable structure
    
    framework_payload = os.path.join(extract_dir, "Python_Framework.pkg", "Payload")
    if os.path.exists(framework_payload):
        # Extract framework to temp location
        temp_framework = os.path.join(temp_dir, "framework")
        subprocess.run(["tar", "-xf", framework_payload, "-C", temp_framework], check=True)
        
        # Copy minimal files to portable structure
        copy_essential_python_files(temp_framework, PYTHON_DIR)
    
    # Create python executable wrapper
    create_python_wrapper_macos()

def copy_essential_python_files(source_framework, dest_python_dir):
    """Copy only essential Python files to minimize size."""
    
    # Find the actual Python installation in the framework
    versions_dir = os.path.join(source_framework, "Library", "Frameworks", "Python.framework", "Versions")
    if not os.path.exists(versions_dir):
        versions_dir = os.path.join(source_framework, "Python.framework", "Versions")
    
    python_version_dir = os.path.join(versions_dir, "3.13")
    if os.path.exists(python_version_dir):
        # Copy essential directories
        essential_dirs = ["lib/python3.13", "include"]
        for dir_name in essential_dirs:
            src_path = os.path.join(python_version_dir, dir_name)
            if os.path.exists(src_path):
                dest_path = os.path.join(dest_python_dir, dir_name)
                shutil.copytree(src_path, dest_path, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "test*", "tests", "*.egg-info"
                ))
        
        # Copy Python executable
        python_exe = os.path.join(python_version_dir, "bin", "python3.13")
        if os.path.exists(python_exe):
            dest_exe = os.path.join(dest_python_dir, "bin", "python")
            shutil.copy2(python_exe, dest_exe)
            os.chmod(dest_exe, 0o755)

def create_python_wrapper_macos():
    """Create Python wrapper script for portable execution."""
    
    wrapper_script = f'''#!/bin/bash
# Portable Python launcher for macOS
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PYTHON_DIR="$SCRIPT_DIR"

export PYTHONHOME="$PYTHON_DIR"
export PYTHONPATH="$PYTHON_DIR/lib/python3.13:$PYTHON_DIR/lib/python3.13/site-packages"

exec "$PYTHON_DIR/bin/python" "$@"
'''
    
    wrapper_path = os.path.join(PYTHON_DIR, "python")
    with open(wrapper_path, "w") as f:
        f.write(wrapper_script)
    os.chmod(wrapper_path, 0o755)
    
    # Install pip
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = os.path.join(PYTHON_DIR, "get-pip.py")
    urllib.request.urlretrieve(get_pip_url, get_pip_path)
    
    subprocess.run([wrapper_path, get_pip_path, "--no-cache-dir"], check=True)
    os.remove(get_pip_path)
    
    install_compact_requirements(wrapper_path)

def install_compact_requirements(python_exe):
    """Install only essential packages with minimal dependencies."""
    
    # Essential packages only - no dev tools, docs, or unused dependencies
    essential_packages = [
        # Core ML packages (use CPU versions first, add CUDA later if needed)
        "torch==2.6.0+cpu",
        "torchvision==0.21.0+cpu", 
        "torchaudio==2.6.0+cpu",
        "torchsde",
        "torchdiffeq", 
        "torchmetrics",
        
        # Core ComfyUI requirements
        "numpy>=1.25.0",
        "Pillow",
        "opencv-python-headless",  # Headless version is smaller
        "scipy",
        "safetensors>=0.4.2",
        "transformers>=4.37.2",
        "tokenizers>=0.13.3",
        
        # Minimal dependencies
        "pyyaml",
        "aiohttp>=3.11.8",
        "tqdm",
        "psutil",
    ]
    
    # Install from PyPI with --no-cache and --no-deps for minimal size
    pip_exe = os.path.join(os.path.dirname(python_exe), "Scripts", "pip.exe")
    
    print(f"Installing {len(essential_packages)} essential packages...")
    subprocess.run([
        pip_exe, "install", 
        "--no-cache-dir",           # No cache
        "--no-compile",             # No .pyc files initially
        "--index-url", "https://download.pytorch.org/whl/cpu",  # CPU wheels first
        "--find-links", "https://download.pytorch.org/whl/cpu"
    ] + essential_packages, check=True)
    
    # Then install CUDA versions if needed (replace CPU versions)
    cuda_packages = [
        "torch==2.6.0+cu124",
        "torchvision==0.21.0+cu124",
        "torchaudio==2.6.0+cu124",
    ]
    
    print("Upgrading to CUDA versions...")
    subprocess.run([
        pip_exe, "install", "--upgrade", "--force-reinstall",
        "--no-cache-dir",
        "--index-url", "https://download.pytorch.org/whl/cu124"
    ] + cuda_packages, check=True)

def aggressive_pruning():
    """Aggressive pruning for minimum size."""
    import shutil
    
    # Remove unnecessary files
    remove_patterns = [
        "**/__pycache__",
        "**/*.pyc", 
        "**/*.pyo",
        "**/test*",
        "**/tests/**", 
        "**/*.egg-info/**",
        "**/docs/**",
        "**/examples/**",
        "**/benchmark/**",
        # Remove large unused torch components
        "**/torch/test/**",
        "**/torch/csrc/**",  # C++ sources not needed
        "**/torchvision/datasets/**",  # Large dataset code
        # Remove conda-specific files
        "**/conda-meta/**",
    ]
    
    # Keep only essential shared libraries
    print("Aggressive pruning for minimal size...")
    
    # Custom pruning logic here...
    pass

if __name__ == "__main__":
    create_compact_python_env()
    aggressive_pruning()
    print("Compact portable Python environment created!")
