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
CHECKPOINT_FILE = os.path.join(ANYMATIX_DIR, ".build_checkpoint")


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
    parser.add_argument(
        "--reset", action="store_true", help="Reset checkpoint and start fresh build"
    )
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


def verify_critical_packages(context: str = "verification") -> None:
    """Verify that critical packages are importable."""
    print(f"[VERIFY] Verifying critical packages during {context}...")
    
    system = platform.system()
    if system == "Windows":
        python_exe = os.path.join(PYTHON_DIR, "python.exe")
    else:
        python_exe = os.path.join(PYTHON_DIR, "bin", "python")
    
    # Map of package name to import name
    critical_packages = {
        "pyyaml": "yaml", 
        "transformers": "transformers",
        "scipy": "scipy", 
        "opencv-python": "cv2",
        "matplotlib": "matplotlib",
        "numpy": "numpy",
        "PIL": "PIL"
    }
    
    failed_packages = []
    for pkg_name, import_name in critical_packages.items():
        try:
            result = run_command([python_exe, "-c", f"import {import_name}; print(f'[OK] {import_name} OK')"], check=False, verbose=False)
            if result.returncode != 0:
                print(f"[FAIL] FAILED: {import_name} (from {pkg_name}) - Return code: {result.returncode}")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}")
                failed_packages.append(pkg_name)
            else:
                print(f"[OK] {import_name} OK")
        except Exception as e:
            print(f"[WARN] Exception verifying {import_name}: {e}")
            failed_packages.append(pkg_name)
    
    if failed_packages:
        print(f"[CRITICAL] CRITICAL: {len(failed_packages)} packages failed verification during {context}: {', '.join(failed_packages)}")
    else:
        print(f"[SUCCESS] All critical packages verified successfully during {context}")
    
    return failed_packages


def run_command(
    cmd: List[str], check: bool = True, shell: bool = False, verbose: bool = None, timeout: int = 600
) -> subprocess.CompletedProcess:
    """Run a command and handle errors."""
    # Auto-enable verbose mode in CI
    if verbose is None:
        verbose = hasattr(save_checkpoint, '_ci_mode') and save_checkpoint._ci_mode
    
    if verbose:
        print(f"[RUN] Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            check=check,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        
        if verbose and result.stdout:
            print(f"[OUT] stdout: {result.stdout[:2000]}{'...' if len(result.stdout) > 2000 else ''}")
        if verbose and result.stderr:
            print(f"[ERR] stderr: {result.stderr[:1000]}{'...' if len(result.stderr) > 1000 else ''}")
            
        return result
        
    except subprocess.TimeoutExpired as e:
        print(f"[TIMEOUT] Command timed out after {timeout}s: {' '.join(cmd)}")
        if check:
            raise
        # Return a dummy CompletedProcess for non-check mode
        return subprocess.CompletedProcess(cmd, 1, "", str(e))
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Command failed: {' '.join(cmd)}")
        print(f"Error: {e}")
        print(f"Output: {e.stdout if hasattr(e, 'stdout') else ''}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else ''}")
        if check:
            raise
        # Return the CompletedProcess from the exception (it has the same fields)
        return subprocess.CompletedProcess(cmd, e.returncode, e.stdout or "", e.stderr or "")


# Resume functionality
def save_checkpoint(step: str) -> None:
    """Save the current build step to a checkpoint file (disabled in CI mode)."""
    # Skip checkpoints in CI mode to ensure clean builds
    if hasattr(save_checkpoint, '_ci_mode') and save_checkpoint._ci_mode:
        return
        
    checkpoint_file = os.path.join(ANYMATIX_DIR, ".build_checkpoint")
    try:
        os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
        with open(checkpoint_file, "w") as f:
            f.write(step)
        print(f"Checkpoint saved: {step}")
    except Exception as e:
        print(f"Warning: Could not save checkpoint: {e}")


def load_checkpoint() -> Optional[str]:
    """Load the last completed build step from checkpoint file (disabled in CI mode)."""
    # Skip checkpoints in CI mode to ensure clean builds
    if hasattr(load_checkpoint, '_ci_mode') and load_checkpoint._ci_mode:
        return None
        
    checkpoint_file = os.path.join(ANYMATIX_DIR, ".build_checkpoint")
    try:
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, "r") as f:
                step = f.read().strip()
            print(f"Found checkpoint: {step}")
            return step
    except Exception as e:
        print(f"Warning: Could not load checkpoint: {e}")
    return None


def should_skip_step(current_step: str, last_completed: Optional[str]) -> bool:
    """Check if the current step should be skipped based on the checkpoint (disabled in CI mode)."""
    # Never skip steps in CI mode to ensure clean builds
    if hasattr(should_skip_step, '_ci_mode') and should_skip_step._ci_mode:
        return False
        
    if not last_completed:
        return False
    
    # Define the order of build steps
    build_steps = [
        "create_python",
        "install_python",
        "install_pytorch", 
        "install_requirements",
        "prune_environment",
        "clone_comfyui",
        "clone_custom_nodes",
        "create_launch_script"
    ]
    
    try:
        last_index = build_steps.index(last_completed)
        current_index = build_steps.index(current_step)
        return current_index <= last_index
    except ValueError:
        return False


def create_portable_python() -> None:
    """Create a portable Python environment using Miniforge."""
    last_checkpoint = load_checkpoint()
    
    print("Creating portable Python environment...")
    
    # Check if we should skip Python environment creation
    if should_skip_step("create_python", last_checkpoint):
        print("Skipping Python environment creation (already completed)")
        return

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

    # Save checkpoint after Python environment creation
    save_checkpoint("create_python")

    # Install required packages
    print("Installing required packages...")
    
    # Check if we should skip Python installation
    if should_skip_step("install_python", last_checkpoint):
        print("Skipping Python installation (already completed)")
    else:
        # Platform-specific installation
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

            # Install Python 3.13 using conda
            print("Installing Python 3.13...")
            try:
                run_command([conda_exe, "install", "-y", "python=3.13"], check=True)
                print("Python 3.13 installed successfully")
            except Exception as e:
                print(f"Error: Could not install Python 3.13 with conda: {e}")
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

            # Install other requirements will be handled in separate checkpoint step below
        else:
            # For Unix-like systems, use the original approach
            conda_exe = os.path.join(PYTHON_DIR, "bin", "conda")
            run_command([conda_exe, "install", "-y", "python=3.13"])

            pip_exe = os.path.join(PYTHON_DIR, "bin", "pip")

            # For macOS with Apple Silicon, optimize NumPy with Accelerate framework
            if platform.system() == "Darwin" and platform.machine() == "arm64":
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
                # Also clean up requirements by removing comments and empty lines
                filtered_requirements = []
                for req in requirements:
                    # Strip whitespace
                    req = req.strip()
                    # Skip empty lines and comment lines
                    if not req or req.startswith("#"):
                        continue
                    # Remove inline comments (everything after #)
                    if "#" in req:
                        req = req.split("#")[0].strip()
                    # Skip if it becomes empty after removing comments
                    if not req:
                        continue
                    # Skip if it's one of the main torch packages we already installed
                    req_name = req.lower().split('>=')[0].split('==')[0].split('~=')[0].split('<')[0].split('>')[0].strip()
                    if req_name in ("torch", "torchvision", "torchaudio"):
                        continue
                    # Final check - only add non-empty, valid-looking requirements
                    if req and not req.isspace() and len(req) > 0:
                        filtered_requirements.append(req)

                if filtered_requirements:
                    run_command([pip_exe, "install"] + filtered_requirements)
            else:
                # For other Unix platforms, install all requirements normally
                run_command([pip_exe, "install", "-r", "requirements.txt"])

        # Save checkpoint after PyTorch installation but before other requirements
        save_checkpoint("install_pytorch")
        
        # Now install other requirements as a separate checkpointed step  
        if should_skip_step("install_requirements", last_checkpoint):
            print("Skipping requirements installation (already completed)")
        else:
            print("Installing remaining requirements...")
            # Requirements installation code goes here (moved from above)
            # This step was previously included in "install_python" checkpoint
            
            # Re-read the requirements filtering logic for the separate step
            try:
                with open("requirements.txt", "r") as f:
                    requirements = f.read().splitlines()

                # Filter out torch, torchvision, torchaudio as they're already installed
                # Also clean up requirements by removing comments and empty lines
                filtered_requirements = []
                for req in requirements:
                    # Strip whitespace
                    req = req.strip()
                    # Skip empty lines and comment lines
                    if not req or req.startswith("#"):
                        continue
                    # Remove inline comments (everything after #)
                    if "#" in req:
                        req = req.split("#")[0].strip()
                    # Skip if it becomes empty after removing comments
                    if not req:
                        continue
                    # Skip if it's one of the main torch packages we already installed
                    req_name = req.lower().split('>=')[0].split('==')[0].split('~=')[0].split('<')[0].split('>')[0].strip()
                    if req_name in ("torch", "torchvision", "torchaudio"):
                        continue
                    # Final check - only add non-empty, valid-looking requirements
                    if req and not req.isspace() and len(req) > 0:
                        filtered_requirements.append(req)

                # Debug output to see what we're about to install
                print(f"Filtered requirements ({len(filtered_requirements)} packages):")
                for i, req in enumerate(filtered_requirements):
                    print(f"  {i+1:2d}: '{req}'")

                if filtered_requirements:
                    print(f"Installing {len(filtered_requirements)} packages...")
                    if platform.system() == "Windows":
                        pip_exe = os.path.join(PYTHON_DIR, "Scripts", "pip.exe")
                        python_exe = os.path.join(PYTHON_DIR, "python.exe")
                    else:
                        pip_exe = os.path.join(PYTHON_DIR, "bin", "pip")
                        python_exe = os.path.join(PYTHON_DIR, "bin", "python")
                    result = run_command([pip_exe, "install"] + filtered_requirements, check=True)
                    print("Requirements installation completed successfully")
                    
                    # Verify critical packages are importable after installation
                    verify_critical_packages("requirements installation")
                    
                    # List installed packages for debugging
                    print("[LIST] Listing all installed packages after requirements installation...")
                    run_command([pip_exe, "list"], check=False, verbose=True)
                else:
                    print("No requirements to install after filtering")
            except Exception as e:
                print(f"Error: Could not install other requirements: {e}")
                print("This is a critical error - the environment may be incomplete")
                # Don't continue with check=False as this would create a broken environment
                raise
                
            save_checkpoint("install_requirements")

        # Save final checkpoint after all Python setup is complete  
        save_checkpoint("install_python")
            
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
        site_packages = os.path.join(PYTHON_DIR, "lib", "python3.13", "site-packages")
        conda_pkgs_dir = os.path.join(PYTHON_DIR, "pkgs")

    # Verify packages BEFORE pruning
    print("[VERIFY] Package verification BEFORE pruning...")
    verify_critical_packages("pre-pruning")

    # 1) Clean conda caches
    try:
        if os.path.exists(conda_exe):
            run_command([conda_exe, "clean", "-a", "-y"], check=False)
    except Exception as e:
        print(f"Warning: conda clean failed: {e}")

    # 2) Purge pip cache (only within the portable environment, not system cache)
    try:
        if os.path.exists(pip_exe):
            # Only purge the portable environment's pip cache, not the user's system cache
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

    # 5) Remove large, unused torch libs (Windows .lib files) with timeout protection
    try:
        torch_lib_dir = os.path.join(site_packages, "torch", "lib")
        if os.path.isdir(torch_lib_dir):
            print(f"Processing torch lib directory: {torch_lib_dir}")
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
                            print(f"Attempting to remove: {lib_path}")
                            # Check file size before removal
                            file_size = os.path.getsize(lib_path)
                            print(f"File size: {file_size / (1024*1024):.1f} MB")
                            
                            # Force close any handles and remove readonly attribute
                            import stat
                            os.chmod(lib_path, stat.S_IWRITE)
                            os.remove(lib_path)
                            print(f"Removed large unused torch lib: {lib_path}")
                        except Exception as e:
                            print(f"Warning: failed removing {lib_path}: {e}")
                            # If removal fails, try to continue with other files
                            continue
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
                            print(f"Attempting to remove: {lib_path}")
                            os.remove(lib_path)
                            print(f"Removed large unused torch archive: {lib_path}")
                        except Exception as e:
                            print(f"Warning: failed removing {lib_path}: {e}")
        else:
            print(f"Torch lib directory not found: {torch_lib_dir}")
    except Exception as e:
        print(f"Warning: torch lib cleanup skipped: {e}")
    
    print("Torch library cleanup completed, proceeding with next step...")

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
    
    # Verify critical packages are still importable after pruning
    print("[VERIFY] Package verification AFTER pruning...")
    failed_packages = verify_critical_packages("post-pruning")
    
    # Check site-packages directory integrity
    print(f"[CHECK] Checking site-packages directory: {site_packages}")
    if os.path.exists(site_packages):
        try:
            pkg_count = len([d for d in os.listdir(site_packages) if os.path.isdir(os.path.join(site_packages, d))])
            print(f"[INFO] Found {pkg_count} package directories in site-packages after pruning")
            
            # Check for specific critical packages
            critical_dirs = ["yaml", "transformers", "scipy", "cv2", "matplotlib", "numpy", "PIL"]
            missing_dirs = []
            for pkg_dir in critical_dirs:
                pkg_path = os.path.join(site_packages, pkg_dir)
                if not os.path.exists(pkg_path):
                    # Also check for egg-info or dist-info directories
                    egg_pattern = f"{pkg_dir}*.egg-info"
                    dist_pattern = f"{pkg_dir}*.dist-info"
                    import glob
                    egg_matches = glob.glob(os.path.join(site_packages, egg_pattern))
                    dist_matches = glob.glob(os.path.join(site_packages, dist_pattern))
                    if not egg_matches and not dist_matches:
                        missing_dirs.append(pkg_dir)
            
            if missing_dirs:
                print(f"[CRITICAL] CRITICAL: Missing package directories after pruning: {missing_dirs}")
            else:
                print("[SUCCESS] All critical package directories found after pruning")
                
        except Exception as e:
            print(f"[WARN] Could not check site-packages integrity: {e}")
    else:
        print(f"[CRITICAL] CRITICAL: site-packages directory missing after pruning: {site_packages}")
    
    # List packages after pruning to see what's left
    if system == "Windows":
        pip_exe = os.path.join(PYTHON_DIR, "Scripts", "pip.exe")
    else:
        pip_exe = os.path.join(PYTHON_DIR, "bin", "pip")
    print("[LIST] Listing packages after pruning...")
    run_command([pip_exe, "list"], check=False, verbose=True)


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
    
    # Use shorter timeout for faster failure detection instead of shallow clone
    # (shallow clone doesn't work well with pinned commits)
    run_command(["git", "clone", COMFYUI_REPO, COMFYUI_DIR], timeout=180)
    run_command(["git", "-C", COMFYUI_DIR, "checkout", comfyui_commit])
    print(f"ComfyUI repository cloned and checked out to {comfyui_commit}.")
    
    # Save checkpoint after ComfyUI cloning
    save_checkpoint("clone_comfyui")


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
        print(f"[DEBUG] Current working directory: {os.getcwd()}")
        print(f"[DEBUG] Target directory: {repo_dir}")
        print(f"[DEBUG] Environment variables: HTTPS_PROXY={os.environ.get('HTTPS_PROXY', 'none')}, HTTP_PROXY={os.environ.get('HTTP_PROXY', 'none')}")
        
        # Use shorter timeout for faster failure detection on problematic repos
        run_command(["git", "clone", repo_url, repo_dir], timeout=180)
        print(f"Clone completed for {repo_url} -> {repo_dir}")

        # Checkout the pinned commit if available
        pin_commit = pin_commit_map.get(repo_url)
        if pin_commit:
            print(f"Checking out pinned commit {pin_commit} for {repo_url}")
            run_command(["git", "-C", repo_dir, "checkout", pin_commit])
            print(f"Checkout completed for {repo_url} at {pin_commit}")
        else:
            print(f"No pin found for {repo_url}, using default branch HEAD.")

    print("Custom node repositories cloned and pinned successfully.")
    
    # Save checkpoint after custom nodes cloning
    save_checkpoint("clone_custom_nodes")


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
            f.write("""# Simple ComfyUI Launcher for Windows
param(
    [int]$Port = 8188
)

$ScriptDir = $PSScriptRoot
$ComfyUIDir = Join-Path $ScriptDir "ComfyUI"
$PythonExe = Join-Path $ScriptDir "python\\python.exe"

Write-Host "Starting ComfyUI on port $Port..."
Write-Host "Python: $PythonExe"
Write-Host "ComfyUI: $ComfyUIDir"


""")

    print("Launch scripts created successfully.")


def create_zip_package() -> str:
    """Create a zip package of the portable ComfyUI."""
    print("Creating zip and tar.bz2 packages...")

    # Get version and platform info
    version = get_version()
    system, arch = get_platform_info()

    # Create zip filename with version and architecture
    zip_filename = f"anymatix-portable-comfyui-{system}-{arch}-v{version}.zip"
    tarbz2_filename = f"anymatix-portable-comfyui-{system}-{arch}-v{version}.tar.bz2"

    # Prefer external zip with maximum compression on all platforms; fallback to Python zipfile
    try:
        print("Attempting external zip -9 for maximum compression...")
        run_command(["zip", "-9", "-r", zip_filename, ANYMATIX_DIR])
        print(f"Zip package created successfully using external zip: {zip_filename}")
    except Exception as e:
        print(f"Warning: external zip failed: {e}")
        print("Falling back to Python's zipfile with compresslevel=9")
        compression_method = zipfile.ZIP_DEFLATED
        # Python 3.13 supports compresslevel for ZIP_DEFLATED
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

    # Create tar.bz2 using external tar if available, fallback to Python tarfile
    try:
        print("Attempting external tar.bz2 for maximum compression...")
        run_command(["tar", "cjf", tarbz2_filename, ANYMATIX_DIR])
        print(f"tar.bz2 package created successfully using external tar: {tarbz2_filename}")
    except Exception as e:
        print(f"Warning: external tar.bz2 failed: {e}")
        print("Falling back to Python's tarfile with bzip2 compression")
        import tarfile
        with tarfile.open(tarbz2_filename, "w:bz2") as tarf:
            tarf.add(ANYMATIX_DIR, arcname=os.path.basename(ANYMATIX_DIR))
        print(f"tar.bz2 package created successfully: {tarbz2_filename}")

    return zip_filename, tarbz2_filename


def split_file(file_path: str, part_size_bytes: int = 100 * 1024 * 1024) -> List[str]:
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

    # Configure checkpoint behavior based on CI mode
    if args.ci:
        print("CI mode detected - checkpoints disabled for clean builds")
        # Set CI mode flag on checkpoint functions
        save_checkpoint._ci_mode = True
        load_checkpoint._ci_mode = True
        should_skip_step._ci_mode = True
        # Clean up any existing checkpoint from previous runs
        checkpoint_path = os.path.join(ANYMATIX_DIR, ".build_checkpoint")
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            print("Removed stale checkpoint file")
    else:
        print("Local build mode - checkpoints enabled for resumable builds")

    # Handle reset flag - clear checkpoint if requested (only in local mode)
    if args.reset and not args.ci and os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("Checkpoint cleared - starting fresh build")

    # Load checkpoint to enable resume functionality (disabled in CI mode)
    last_checkpoint = load_checkpoint()
    if last_checkpoint:
        print(f"Resuming from checkpoint: {last_checkpoint}")
    else:
        if args.ci:
            print("Starting clean CI build")
        else:
            print("Starting fresh build (no checkpoint found)")

    # Create portable Python environment
    if should_skip_step("create_python", last_checkpoint):
        print("Skipping Python environment creation (already completed)")
    else:
        create_portable_python()

    # Prune environment to reduce artifact size (all platforms)
    if should_skip_step("prune_environment", last_checkpoint):
        print("Skipping environment pruning (already completed)")
    else:
        prune_environment()
        save_checkpoint("prune_environment")

    # Clone ComfyUI repository
    if should_skip_step("clone_comfyui", last_checkpoint):
        print("Skipping ComfyUI cloning (already completed)")
    else:
        clone_comfyui()

    # Clone custom node repositories
    if should_skip_step("clone_custom_nodes", last_checkpoint):
        print("Skipping custom nodes cloning (already completed)")
    else:
        clone_custom_nodes()

    # Create launch script
    if should_skip_step("create_launch_script", last_checkpoint):
        print("Skipping launch script creation (already completed)")
    else:
        create_launch_script()
        save_checkpoint("create_launch_script")

    # Copy requirements.txt to the anymatix directory for user reference
    if should_skip_step("copy_requirements", last_checkpoint):
        print("Skipping requirements.txt copying (already completed)")
    else:
        copy_requirements_txt()
        save_checkpoint("copy_requirements")

    # Create zip package
    zip_filename, tarbz2_filename = None, None
    if should_skip_step("create_zip", last_checkpoint):
        print("Skipping zip/tar.bz2 creation (already completed)")
        import glob
        zip_files = glob.glob("anymatix-*.zip")
        tarbz2_files = glob.glob("anymatix-*.tar.bz2")
        if zip_files:
            zip_filename = zip_files[0]
            print(f"Found existing zip file: {zip_filename}")
        if tarbz2_files:
            tarbz2_filename = tarbz2_files[0]
            print(f"Found existing tar.bz2 file: {tarbz2_filename}")
    else:
        zip_filename, tarbz2_filename = create_zip_package()
        save_checkpoint("create_zip")

    # If we're on CI, split both zip and tar.bz2 into 100MB parts for CI uploads
    for filename in [zip_filename, tarbz2_filename]:
        if args.ci and filename and os.path.exists(filename):
            print(f"Splitting {filename} into 100MB parts for CI uploads...")
            parts = split_file(filename, 100 * 1024 * 1024)
            if parts:
                try:
                    os.remove(filename)
                except Exception as e:
                    print(f"Warning: failed to remove original archive {filename}: {e}")
                print("Created parts:")
                for p in parts:
                    print(f" - {p}")
            else:
                print(f"Archive {filename} smaller than 100MB; no splitting performed.")

    # Push to GitHub if requested
    if args.push:
        push_to_github(args.branch)

    # Trigger GitHub workflow if requested
    if args.trigger_workflow:
        trigger_github_workflow(args.workflow, args.branch)

    # Final verification before completion
    print("[VERIFY] Final verification of critical packages...")
    final_failed = verify_critical_packages("final build completion")
    if final_failed:
        print(f"[WARNING] WARNING: Build completed but {len(final_failed)} critical packages are missing!")
        print("This may cause runtime failures. Check the logs above for details.")

    # Clear checkpoint on successful completion (only in local mode)
    if not args.ci and os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("Build completed successfully - checkpoint cleared")

    print("Portable ComfyUI package created successfully.")


if __name__ == "__main__":
    main()
