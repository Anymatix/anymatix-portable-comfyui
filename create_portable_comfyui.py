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
    """Get the latest anymatix_version from PIN.json (lexicographically highest)."""
    if not os.path.exists("PIN.json"):
        raise RuntimeError("PIN.json not found; cannot determine version.")
    with open("PIN.json", "r") as f:
        pins = json.load(f)
    # Find the lexicographically highest version
    versions = [pin.get("anymatix_version", "") for pin in pins if pin.get("anymatix_version")]
    if not versions:
        raise RuntimeError("No anymatix_version found in PIN.json.")
    return sorted(versions)[-1]


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
            run_command([conda_exe, "init", "cmd.exe"], check=True)
            print("Conda initialized successfully")
        except Exception as e:
            print(f"Warning: Could not initialize conda: {e}")
            print("This may affect some conda operations but installation can continue...")

        # Install Python 3.10 using conda
        print("Installing Python 3.10...")
        try:
            run_command([conda_exe, "install", "-y", "python=3.10"], check=True)
            print("Python 3.10 installed successfully")
        except Exception as e:
            print(f"Error: Could not install Python 3.10 with conda: {e}")
            print("This is a critical error - cannot continue without Python")
            raise

        # Install PyTorch with CUDA support for Windows
        print("Installing PyTorch with CUDA support for Windows...")
        try:
            run_command([
                pip_exe, "install", "torch", "torchvision", "torchaudio", 
                "--index-url", "https://download.pytorch.org/whl/cu124"
            ], check=True)
            print("PyTorch with CUDA installed successfully")
        except Exception as e:
            print(f"Warning: Could not install PyTorch with CUDA: {e}")
            print("Falling back to CPU-only PyTorch...")
            run_command([pip_exe, "install", "torch", "torchvision", "torchaudio"], check=True)
            print("CPU-only PyTorch installed successfully")

        # Install other requirements (excluding PyTorch packages)
        print("Installing other requirements...")
        try:
            with open("requirements.txt", "r") as f:
                requirements = f.read().splitlines()

            # Filter out torch, torchvision, torchaudio as they're already installed
            filtered_requirements = [
                req
                for req in requirements
                if not req.startswith(("torch", "torchvision", "torchaudio", "#"))
            ]

            if filtered_requirements:
                result = run_command([pip_exe, "install"] + filtered_requirements, check=True)
                print("Requirements installation completed successfully")
        except Exception as e:
            print(f"Error: Could not install other requirements: {e}")
            print("This is a critical error - the environment may be incomplete")
            # Don't continue with check=False as this would create a broken environment
            raise
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


def prune_environment() -> None:
    """Prune caches and non-runtime files to reduce bundle size (all platforms)."""
    print("Pruning environment to reduce size...")

    system = platform.system()

    # Resolve conda and pip executables
    if system == "Windows":
        conda_exe = os.path.join(PYTHON_DIR, "Scripts", "conda.exe")
        pip_exe = os.path.join(PYTHON_DIR, "Scripts", "pip.exe")
        site_packages = os.path.join(PYTHON_DIR, "Lib", "site-packages")
        conda_pkgs_dir = os.path.join(PYTHON_DIR, "pkgs")
    else:
        conda_exe = os.path.join(PYTHON_DIR, "bin", "conda")
        pip_exe = os.path.join(PYTHON_DIR, "bin", "pip")
        # Typical conda prefix layout on Unix
        site_packages = os.path.join(PYTHON_DIR, "lib", "python3.10", "site-packages")
        conda_pkgs_dir = os.path.join(PYTHON_DIR, "pkgs")

    # 1) Clean conda caches
    try:
        if os.path.exists(conda_exe):
            run_command([conda_exe, "clean", "-a", "-y"], check=False)
    except Exception as e:
        print(f"Warning: conda clean failed: {e}")

    # 2) Purge pip cache
    try:
        if os.path.exists(pip_exe):
            run_command([pip_exe, "cache", "purge"], check=False)
    except Exception as e:
        print(f"Warning: pip cache purge failed: {e}")

    # 3) Remove conda pkgs dir if present
    try:
        if os.path.isdir(conda_pkgs_dir):
            shutil.rmtree(conda_pkgs_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: removing pkgs dir failed: {e}")

    # Prepare exclusions (do not prune anything inside comfyui_embedded_docs)
    comfy_docs_pkg_dir = os.path.join(site_packages, "comfyui_embedded_docs")
    exclude_prefixes = [os.path.abspath(comfy_docs_pkg_dir)]

    # 4) Remove __pycache__, *.pyc, *.pyo across the anymatix tree (except excluded dirs)
    for root, dirs, files in os.walk(ANYMATIX_DIR):
        # Skip excluded subtrees entirely
        abs_root = os.path.abspath(root)
        if any(abs_root.startswith(p) for p in exclude_prefixes):
            continue
        # Remove __pycache__ directories
        if "__pycache__" in dirs:
            try:
                shutil.rmtree(os.path.join(root, "__pycache__"), ignore_errors=True)
            except Exception:
                pass
        # Remove compiled python files
        for fname in list(files):
            if fname.endswith((".pyc", ".pyo")):
                fpath = os.path.join(root, fname)
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    # 5) Remove large, unused torch libs (Windows .lib files)
    try:
        torch_lib_dir = os.path.join(site_packages, "torch", "lib")
        if os.path.isdir(torch_lib_dir):
            # Windows: remove .lib import libraries (not needed at runtime)
            large_libs_win = [
                "dnnl.lib",
                "libprotoc.lib",
                "libprotobuf.lib",
            ]
            if system == "Windows":
                for lib in large_libs_win:
                    lib_path = os.path.join(torch_lib_dir, lib)
                    if os.path.isfile(lib_path):
                        try:
                            os.remove(lib_path)
                            print(f"Removed large unused torch lib: {lib_path}")
                        except Exception as e:
                            print(f"Warning: failed removing {lib_path}: {e}")
            else:
                # macOS/Linux: remove static archives if present (keep .dylib/.so)
                large_archives_unix = [
                    "libdnnl.a",
                    "libprotoc.a",
                    "libprotobuf.a",
                ]
                for lib in large_archives_unix:
                    lib_path = os.path.join(torch_lib_dir, lib)
                    if os.path.isfile(lib_path):
                        try:
                            os.remove(lib_path)
                            print(f"Removed large unused torch archive: {lib_path}")
                        except Exception as e:
                            print(f"Warning: failed removing {lib_path}: {e}")
    except Exception as e:
        print(f"Warning: torch lib cleanup skipped: {e}")

    # 6) Trim non-runtime folders in site-packages (if exists)
    trim_dirs = {
        "tests",
        "test",
        "Testing",
        "benchmarks",
        "examples",
        "example",
        "docs",
        "doc",
        "tutorials",
        "samples",
        "sample_data",
    }
    if os.path.isdir(site_packages):
        for root, dirs, _ in os.walk(site_packages):
            # Skip comfyui_embedded_docs entirely
            try:
                abs_root = os.path.abspath(root)
            except Exception:
                abs_root = root
            if any(abs_root.startswith(p) for p in exclude_prefixes):
                continue

            # Determine if we're inside numpy; don't remove its tests (SciPy imports numpy._core.tests at runtime)
            try:
                rel = os.path.relpath(root, site_packages)
            except ValueError:
                rel = ""
            top_level = rel.split(os.sep)[0] if rel and rel != os.curdir else ""
            inside_numpy = top_level == "numpy"

            for d in list(dirs):
                if d in trim_dirs:
                    # Keep numpy tests; other trim targets (docs/examples/etc.) are safe to remove
                    if d == "tests" and inside_numpy:
                        continue
                    try:
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    except Exception:
                        pass
    print("Pruning complete.")


def clone_comfyui() -> None:
    """Clone the ComfyUI repository."""
    print("Cloning ComfyUI repository...")
    # Get current Anymatix version
    anymatix_version = get_version()
    # Load PIN.json and find the matching comfyui_commit
    with open("PIN.json", "r") as pf:
        pins = json.load(pf)
    comfyui_commit = None
    for pin in pins:
        if pin.get("anymatix_version", "").strip() == anymatix_version:
            comfyui_commit = pin.get("comfyui_commit")
            break
    if not comfyui_commit:
        raise RuntimeError(f"No comfyui_commit found in PIN.json for Anymatix version {anymatix_version}")
    run_command(["git", "clone", COMFYUI_REPO, COMFYUI_DIR])
    run_command(["git", "-C", COMFYUI_DIR, "checkout", comfyui_commit])
    print(f"ComfyUI repository cloned and checked out to {comfyui_commit}.")


def clone_custom_nodes() -> None:
    """Clone the custom node repositories."""
    print("Cloning custom node repositories...")

    # Create custom_nodes directory if it doesn't exist
    os.makedirs(CUSTOM_NODES_DIR, exist_ok=True)

    # Read repos.json
    with open("repos.json", "r") as f:
        repos = json.load(f)

    # Read PIN.json for current version pins
    anymatix_version = get_version()
    pin_commit_map = {}
    if os.path.exists("PIN.json"):
        with open("PIN.json", "r") as pf:
            pins = json.load(pf)
        for pin in pins:
            if pin.get("anymatix_version", "").strip() == anymatix_version:
                for node in pin.get("custom_nodes", []):
                    pin_commit_map[node["url"]] = node["commit"]
                break

    # Clone each repository and check out the pinned commit if available
    for repo in repos:
        repo_url = repo["url"]
        repo_name = os.path.basename(repo_url).replace(".git", "")
        repo_dir = os.path.join(CUSTOM_NODES_DIR, repo_name)

        print(f"Cloning {repo_url}...")
        run_command(["git", "clone", repo_url, repo_dir])

        # Checkout the pinned commit if available
        pin_commit = pin_commit_map.get(repo_url)
        if pin_commit:
            print(f"Checking out pinned commit {pin_commit} for {repo_url}")
            run_command(["git", "-C", repo_dir, "checkout", pin_commit])
        else:
            print(f"No pin found for {repo_url}, using default branch HEAD.")

    print("Custom node repositories cloned and pinned successfully.")


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
        launch_script_path = os.path.join(ANYMATIX_DIR, "anymatix_comfyui_wrapper.ps1")

        with open(launch_script_path, "w", encoding='utf-8') as f:
            f.write("""#Requires -Version 5.1

<#
.SYNOPSIS
    ComfyUI Launcher with Robust Process Management
    
.DESCRIPTION
    A PowerShell-based launcher for ComfyUI that provides robust process tree management
    using Windows Job Objects. This script replaces traditional batch file launchers
    with comprehensive process lifecycle management.
    
    Key Features:
    - Automatic process tree termination when parent process exits
    - Windows Job Object integration for reliable cleanup
    - Portable Python environment detection and usage
    - Background monitoring without polling overhead
    - Comprehensive error handling and cleanup
    
    Design Philosophy:
    The script uses Windows Job Objects to ensure all child processes (ComfyUI Python
    processes) are automatically terminated when the parent application exits, even
    if the parent exits unexpectedly. Parent process monitoring uses efficient
    WaitForSingleObject with infinite timeout instead of polling, eliminating
    race conditions and reducing CPU overhead.
    
.PARAMETER Port
    The port number for ComfyUI to listen on
    Default: 8188
    
.PARAMETER Help
    Display detailed help information about this script
    
.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "anymatix_comfyui_wrapper.ps1" -Port 8188
    
    Launches ComfyUI on port 8188 with automatic process management
    
.EXAMPLE 
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "anymatix_comfyui_wrapper.ps1" -Port 9800
    
    Launches ComfyUI on port 9800 with automatic process management
    
.NOTES
    Requires PowerShell 5.1 or higher
    Designed for Windows environments with Job Object support
    Expects ComfyUI directory structure with portable Python environment
#>

[CmdletBinding(DefaultParameterSetName='Run')]
param(
    [Parameter(ParameterSetName='Run')]
    [int]$Port = 8188,
    
    [Parameter(ParameterSetName='Help', Mandatory)]
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

# Windows Job Objects P/Invoke definitions for process tree management
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class JobObject
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateJobObjectW(IntPtr lpJobAttributes, string lpName);

    [DllImport("kernel32.dll")]
    public static extern bool SetInformationJobObject(IntPtr hJob, int JobObjectInformationClass,
        IntPtr lpJobObjectInformation, uint cbJobObjectInformationLength);

    [DllImport("kernel32.dll")]
    public static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr hObject);

    [DllImport("kernel32.dll")]
    public static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

    [DllImport("kernel32.dll")]
    public static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    public const int JobObjectExtendedLimitInformation = 9;
    public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
    public const uint SYNCHRONIZE = 0x00100000;
    public const uint WAIT_OBJECT_0 = 0x00000000;
    public const uint INFINITE = 0xFFFFFFFF;
}
"@

# Global variables for process and job management
$global:JobHandle = [IntPtr]::Zero
$global:Process = $null
$global:ProcessPID = $null
$global:ParentMonitorJob = $null
$global:OutputReader = $null
$global:ErrorReader = $null

# Process cleanup function - ensures all child processes are terminated
function Cleanup {
    Write-Host "Performing cleanup..." -ForegroundColor Yellow
    
    # Stop parent monitoring job if running
    if ($global:ParentMonitorJob) {
        try {
            $global:ParentMonitorJob | Stop-Job -Force
            $global:ParentMonitorJob | Remove-Job -Force
        } catch { 
            # Silent error handling for job cleanup
        }
        $global:ParentMonitorJob = $null
    }
    
    # Stop async readers to prevent hanging processes
    if ($global:Process) {
        try {
            $global:Process.CancelOutputRead()
            $global:Process.CancelErrorRead()
        } catch { 
            # Silent error handling for reader cleanup
        }
    }
    
    # Dispose readers to free resources
    if ($global:OutputReader) {
        try { $global:OutputReader.Dispose() } catch { }
        $global:OutputReader = $null
    }
    if ($global:ErrorReader) {
        try { $global:ErrorReader.Dispose() } catch { }
        $global:ErrorReader = $null
    }
    
    # First attempt: Kill the process tree using taskkill (most reliable)
    if ($global:ProcessPID) {
        try {
            Write-Host "Terminating ComfyUI process tree..." -ForegroundColor Yellow
            Start-Process "taskkill" -ArgumentList "/F", "/T", "/PID", $global:ProcessPID -Wait -WindowStyle Hidden -NoNewWindow
            Start-Sleep -Milliseconds 500  # Allow time for termination
        } catch {
            Write-Host "Process termination failed: $_" -ForegroundColor Yellow
        }
    }
    
    # Second attempt: Close job handle (kills all processes in the job)
    if ($global:JobHandle -ne [IntPtr]::Zero) {
        Write-Host "Closing job handle..." -ForegroundColor Yellow
        [JobObject]::CloseHandle($global:JobHandle) | Out-Null
        $global:JobHandle = [IntPtr]::Zero
    }
    
    # Final cleanup: Process object disposal
    if ($global:Process) {
        try { 
            if (-not $global:Process.HasExited) {
                $global:Process.Kill($true)
                $global:Process.WaitForExit(2000)
            }
            $global:Process.Dispose() 
        } catch { 
            # Silent error handling for process disposal
        }
        $global:Process = $null
    }
    
    Write-Host "Cleanup completed" -ForegroundColor Green
}

# Event handlers for graceful shutdown on various exit scenarios
$null = Register-ObjectEvent -InputObject ([System.Console]) -EventName CancelKeyPress -Action {
    Write-Host "`nCtrl+C detected - cleaning up..." -ForegroundColor Yellow
    Cleanup
    [Environment]::Exit(0)
}

try {
    # Resolve script directory and set up logging
    $ScriptDir = $PSScriptRoot
    if (-not $ScriptDir) {
        $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    
    Write-Host "=== ComfyUI Launcher Starting ===" -ForegroundColor Green
    Write-Host "Script directory: $ScriptDir" -ForegroundColor Green
    Write-Host "ComfyUI Port: $Port" -ForegroundColor Green
    
    # Path validation - ensure all required components exist
    $ComfyUIDir = Join-Path $ScriptDir "ComfyUI"
    $PythonExe = Join-Path $ScriptDir "python\\python.exe"
    $MainPy = Join-Path $ComfyUIDir "main.py"
    
    if (-not (Test-Path $ComfyUIDir -PathType Container)) {
        throw "ComfyUI directory not found: $ComfyUIDir"
    }
    
    if (-not (Test-Path $PythonExe -PathType Leaf)) {
        throw "Python executable not found: $PythonExe"
    }
    
    if (-not (Test-Path $MainPy -PathType Leaf)) {
        throw "ComfyUI main.py not found: $MainPy"
    }
    
    Write-Host "All required files validated" -ForegroundColor Green
    
    # Parent process detection for automatic termination
    $CurrentPID = [System.Diagnostics.Process]::GetCurrentProcess().Id
    $ParentProcess = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $CurrentPID" | Select-Object -ExpandProperty ParentProcessId
    
    if (-not $ParentProcess) {
        throw "Could not determine parent process ID for monitoring"
    }
    
    Write-Host "Parent process monitoring enabled (PID: $ParentProcess)" -ForegroundColor Green
    
    # Verify parent process exists and get detailed info
    try {
        $parentProc = [System.Diagnostics.Process]::GetProcessById($ParentProcess)
        $parentName = $parentProc.ProcessName
        Write-Host "Parent process verified: $parentName (PID: $ParentProcess)" -ForegroundColor Green
    }
    catch {
        Write-Warning "Cannot access parent process $ParentProcess - it may have already exited"
    }
    
    # Windows Job Object creation - ensures process tree cleanup
    $global:JobHandle = [JobObject]::CreateJobObjectW([IntPtr]::Zero, $null)
    if ($global:JobHandle -eq [IntPtr]::Zero) {
        throw "Failed to create job object"
    }
    
    Write-Host "Job object created successfully" -ForegroundColor Green
    
    # Configure job object to terminate all child processes when job handle is closed
    $extendedInfo = New-Object JobObject+JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    $extendedInfo.BasicLimitInformation.LimitFlags = [JobObject]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    
    $extendedInfoSize = [System.Runtime.InteropServices.Marshal]::SizeOf($extendedInfo)
    $extendedInfoPtr = [System.Runtime.InteropServices.Marshal]::AllocHGlobal($extendedInfoSize)
    
    try {
        [System.Runtime.InteropServices.Marshal]::StructureToPtr($extendedInfo, $extendedInfoPtr, $false)
        
        $result = [JobObject]::SetInformationJobObject(
            $global:JobHandle, 
            [JobObject]::JobObjectExtendedLimitInformation, 
            $extendedInfoPtr, 
            $extendedInfoSize
        )
        
        if (-not $result) {
            throw "Failed to set job object information"
        }
        
        Write-Host "Job object configured for automatic process tree termination" -ForegroundColor Green
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::FreeHGlobal($extendedInfoPtr)
    }
    
    # Parent process monitoring setup - uses efficient blocking wait instead of polling
    $parentWaitScript = {
        param($ParentPID)
        
        # P/Invoke definitions for efficient parent process monitoring
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class ParentWaiter
{
    [DllImport("kernel32.dll")]
    public static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

    [DllImport("kernel32.dll")]
    public static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr hObject);

    public const uint SYNCHRONIZE = 0x00100000;
    public const uint WAIT_OBJECT_0 = 0x00000000;
    public const uint INFINITE = 0xFFFFFFFF;
}
"@

        $parentHandle = [ParentWaiter]::OpenProcess([ParentWaiter]::SYNCHRONIZE, $false, $ParentPID)
        
        if ($parentHandle -ne [IntPtr]::Zero) {
            # Efficient blocking wait - no CPU usage until parent exits
            try {
                [ParentWaiter]::WaitForSingleObject($parentHandle, [ParentWaiter]::INFINITE) | Out-Null
                return $true
            }
            finally {
                [ParentWaiter]::CloseHandle($parentHandle) | Out-Null
            }
        }
        else {
            # Fallback: polling method if handle opening fails
            while ($true) {
                try {
                    $proc = [System.Diagnostics.Process]::GetProcessById($ParentPID)
                    if ($proc.HasExited) {
                        return $true
                    }
                }
                catch {
                    # Parent process no longer exists
                    return $true
                }
                Start-Sleep -Seconds 1
            }
        }
        
        return $false
    }
    
    # Start parent monitoring in background job
    $global:ParentMonitorJob = Start-Job -ScriptBlock $parentWaitScript -ArgumentList $ParentProcess
    
    Write-Host "Parent process monitoring started" -ForegroundColor Green
    
    # ComfyUI process configuration
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $PythonExe
    $processInfo.Arguments = "main.py --enable-cors-header `"*`" --force-fp16 --preview-method=none --port=$Port"
    $processInfo.WorkingDirectory = $ComfyUIDir
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.CreateNoWindow = $false  # Allow console window for ComfyUI output
    
    Write-Host "Starting ComfyUI process..." -ForegroundColor Green
    Write-Host "Command: $($processInfo.FileName) $($processInfo.Arguments)" -ForegroundColor Cyan
    Write-Host "Working Directory: $($processInfo.WorkingDirectory)" -ForegroundColor Cyan
    
    # Create and configure the process object
    $global:Process = New-Object System.Diagnostics.Process
    $global:Process.StartInfo = $processInfo
    
    # Set up async output reading for real-time display
    $global:Process.EnableRaisingEvents = $true
    
    # Start the ComfyUI process
    $started = $global:Process.Start()
    if (-not $started) {
        throw "Failed to start ComfyUI process"
    }
    
    $processPID = $global:Process.Id
    Write-Host "ComfyUI process started with PID: $processPID" -ForegroundColor Green
    
    # Assign process to job object for automatic cleanup
    $assignResult = [JobObject]::AssignProcessToJobObject($global:JobHandle, $global:Process.Handle)
    if (-not $assignResult) {
        Write-Warning "Failed to assign process to job object - cleanup may not be automatic"
        Write-Host "Will use alternative cleanup methods" -ForegroundColor Yellow
    }
    else {
        Write-Host "Process assigned to job object - automatic cleanup enabled" -ForegroundColor Green
    }
    
    # Store process ID for cleanup operations
    $global:ProcessPID = $processPID
    
    # Begin async output reading for real-time console display
    $global:Process.BeginOutputReadLine()
    $global:Process.BeginErrorReadLine()
    
    # Event handlers for output streams - filter duplicate stderr messages
    Register-ObjectEvent -InputObject $global:Process -EventName OutputDataReceived -Action {
        $data = $Event.SourceEventArgs.Data
        if ($data) {
            Write-Host $data
        }
    } | Out-Null
    
    Register-ObjectEvent -InputObject $global:Process -EventName ErrorDataReceived -Action {
        $data = $Event.SourceEventArgs.Data
        # Filter common duplicate messages that appear in both stdout and stderr
        if ($data -and $data -notmatch "^(Total VRAM|pytorch version|Set vram state|Device:|Using pytorch|Python version|ComfyUI version|Import times|Starting server|To see the GUI|Context impl|Will assume|No target revision)") {
            Write-Host $data -ForegroundColor Red
        }
    } | Out-Null
    
    # Process exit event handler
    Register-ObjectEvent -InputObject $global:Process -EventName Exited -Action {
        $exitCode = $Event.Sender.ExitCode
        Write-Host "ComfyUI process exited with code: $exitCode" -ForegroundColor Yellow
        [Environment]::Exit($exitCode)
    } | Out-Null
    
    Write-Host "ComfyUI is starting up..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
    
    # Main monitoring loop - wait for parent exit or ComfyUI completion
    while ($true) {
        # Check if parent monitoring completed (parent exited)
        if ($global:ParentMonitorJob.State -eq "Completed") {
            Write-Host "Parent process exited - shutting down ComfyUI" -ForegroundColor Yellow
            break
        }
        
        # Check if parent monitoring failed
        if ($global:ParentMonitorJob.State -eq "Failed") {
            Write-Host "Parent monitoring failed - shutting down ComfyUI" -ForegroundColor Red
            break
        }
        
        # Check if ComfyUI process exited naturally
        if ($global:Process.HasExited) {
            Write-Host "ComfyUI process exited naturally" -ForegroundColor Green
            break
        }
        
        Start-Sleep -Seconds 1
    }
    
    # Determine exit reason and perform cleanup
    $exitCode = 0
    if ($global:Process -and -not $global:Process.HasExited) {
        # Process is still running - we're exiting due to parent termination
        Write-Host "Terminating ComfyUI due to parent exit..." -ForegroundColor Yellow
    }
    elseif ($global:Process) {
        $exitCode = $global:Process.ExitCode
        Write-Host "ComfyUI exited with code: $exitCode" -ForegroundColor Yellow
    }
    
    # Cleanup and exit
    Cleanup
    
    # Force exit to ensure script terminates
    Write-Host "Script exiting with code: $exitCode" -ForegroundColor Green
    [Environment]::Exit($exitCode)
}
catch {
    Write-Error "Error in ComfyUI launcher: $_"
    Write-Error $_.ScriptStackTrace
    Cleanup
    [Environment]::Exit(1)
}
finally {
    # Ensure cleanup always runs
    Write-Host "Finally block - ensuring cleanup" -ForegroundColor Yellow
    Cleanup
}
""")

    print("Launch scripts created successfully.")


def create_zip_package() -> str:
    """Create a zip package of the portable ComfyUI."""
    print("Creating zip package...")

    # Get version and platform info
    version = get_version()
    system, arch = get_platform_info()

    # Create zip filename with version and architecture
    zip_filename = f"anymatix-portable-comfyui-{system}-{arch}-v{version}.zip"

    # Prefer external zip with maximum compression on all platforms; fallback to Python zipfile
    try:
        print("Attempting external zip -9 for maximum compression...")
        run_command(["zip", "-9", "-r", zip_filename, ANYMATIX_DIR])
        print(f"Zip package created successfully using external zip: {zip_filename}")
        return zip_filename
    except Exception as e:
        print(f"Warning: external zip failed: {e}")
        print("Falling back to Python's zipfile with compresslevel=9")

    compression_method = zipfile.ZIP_DEFLATED
    # Python 3.10 supports compresslevel for ZIP_DEFLATED
    with zipfile.ZipFile(zip_filename, "w", compression_method, compresslevel=9) as zipf:
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


def split_file(file_path: str, part_size_bytes: int = 512 * 1024 * 1024) -> List[str]:
    """Split a file into fixed-size parts. Returns the list of created part filenames.

    Parts are named: <file>.part01, <file>.part02, ...
    """
    parts: List[str] = []
    total_size = os.path.getsize(file_path)
    if total_size == 0:
        return parts

    idx = 1
    with open(file_path, "rb") as src:
        while True:
            chunk = src.read(part_size_bytes)
            if not chunk:
                break
            part_name = f"{file_path}.part{idx:02d}"
            with open(part_name, "wb") as dst:
                dst.write(chunk)
            parts.append(part_name)
            print(f"Created part {part_name} ({len(chunk)} bytes)")
            idx += 1
    return parts


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


def copy_requirements_txt() -> None:
    """Copy requirements.txt to the anymatix directory for user reference."""
    print("Copying requirements.txt to anymatix directory...")
    
    # Source requirements.txt (in the current working directory)
    source_requirements = "requirements.txt"
    
    # Destination path in the anymatix directory
    dest_requirements = os.path.join(ANYMATIX_DIR, "requirements.txt")
    
    try:
        if os.path.exists(source_requirements):
            shutil.copy2(source_requirements, dest_requirements)
            print(f"Successfully copied requirements.txt to {dest_requirements}")
        else:
            print(f"Warning: requirements.txt not found at {source_requirements}")
    except Exception as e:
        print(f"Warning: Failed to copy requirements.txt: {e}")


def main() -> None:
    """Main function."""
    args = parse_args()

    # Create anymatix directory
    os.makedirs(ANYMATIX_DIR, exist_ok=True)

    # Create portable Python environment
    create_portable_python()

    # Prune environment to reduce artifact size (all platforms)
    prune_environment()

    # Clone ComfyUI repository
    clone_comfyui()

    # Clone custom node repositories
    clone_custom_nodes()

    # Create launch script
    create_launch_script()

    # Copy requirements.txt to the anymatix directory for user reference
    copy_requirements_txt()

    # Create zip package
    zip_filename = create_zip_package()

    # If we're on CI, rename the zip file to a standard name for the artifact
    if args.ci:
        # Split zip into 512MB parts to bypass platform limits
        print("Splitting zip into 512MB parts for CI uploads...")
        parts = split_file(zip_filename, 512 * 1024 * 1024)
        if parts:
            # Remove the original large zip to avoid double uploads
            try:
                os.remove(zip_filename)
            except Exception as e:
                print(f"Warning: failed to remove original zip {zip_filename}: {e}")
            print("Created parts:")
            for p in parts:
                print(f" - {p}")
        else:
            print("Zip smaller than 512MB; no splitting performed.")

    # Push to GitHub if requested
    if args.push:
        push_to_github(args.branch)

    # Trigger GitHub workflow if requested
    if args.trigger_workflow:
        trigger_github_workflow(args.workflow, args.branch)

    print("Portable ComfyUI package created successfully.")


if __name__ == "__main__":
    main()
