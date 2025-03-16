# Anymatix Portable ComfyUI Implementation

This document describes the implementation of the Anymatix Portable ComfyUI package.

## Overview

The Anymatix Portable ComfyUI package is a self-contained, portable distribution of ComfyUI that includes:

1. A portable Python environment with all required dependencies
2. The ComfyUI repository
3. Custom node repositories
4. Platform-specific launch scripts (Windows, macOS)

The package is designed to be platform-independent and can be run on macOS and Windows.

## Implementation Details

### Portable Python Environment

The portable Python environment is created using Miniforge, a minimal installer for conda. Miniforge is chosen because:

- It's lightweight compared to Anaconda
- It uses conda-forge as the default channel, which has a wide range of packages
- It's available for all major platforms (macOS, Windows, Linux)
- It has a permissive license that allows for redistribution

The Python environment includes all the packages listed in `requirements.txt`.

### Apple Silicon Optimization

For macOS with Apple Silicon (M1/M2/M3), the Python environment is specially optimized:

- NumPy is configured to use the Apple Accelerate framework via the `libblas=*=*accelerate` package, which provides significant performance improvements for linear algebra operations
- The `libblas` package is pinned to ensure it always uses the Accelerate framework
- PyTorch is installed with MPS (Metal Performance Shaders) support, enabling GPU acceleration on Apple Silicon
- The installation process is customized to ensure these optimizations are properly applied

These optimizations result in better performance for tensor operations and neural network inference on Apple Silicon Macs.

### ComfyUI Repository

The ComfyUI repository is cloned from https://github.com/comfyanonymous/ComfyUI.git. This repository contains the core ComfyUI application.

### Custom Node Repositories

Custom node repositories are cloned from the URLs specified in `repos.json`. These repositories contain additional nodes that extend the functionality of ComfyUI.

### Launch Scripts

Platform-specific launch scripts are created:

1. **macOS**: `anymatix_comfyui_darwin`
   - Changes to the ComfyUI directory
   - Checks for and removes the quarantine attribute if present
   - Launches ComfyUI with the portable Python
   - Passes the appropriate command-line arguments

2. **Windows**: `anymatix_comfyui_windows.bat`
   - Windows batch file that performs the same functions as the Unix scripts

All launch scripts accept an optional port number as the first argument, defaulting to 8188 if not provided.

#### macOS Quarantine Handling

On macOS, downloaded applications are marked with a quarantine attribute (`com.apple.quarantine`) as a security measure. This can prevent the portable ComfyUI package from running properly. The macOS launch script includes logic to:

1. Check if the quarantine attribute exists on the package directory
2. If found, attempt to remove it using the `xattr` command
3. Provide clear instructions if manual removal is needed

This approach ensures that the quarantine attribute is only removed when necessary, avoiding unnecessary operations on subsequent launches.

### Version Management

The package version is managed using a `VERSION.txt` file in the root of the repository. This file contains a semantic version number (currently `1.0.0`) that is used in the zip filename and for GitHub releases.

## Building the Package

The package is built using the `create_portable_comfyui.py` script. This script:

1. Creates the portable Python environment
2. Clones the ComfyUI repository
3. Clones the custom node repositories
4. Creates platform-specific launch scripts
5. Packages everything into a zip file with version and architecture information

The script can be run locally or on GitHub CI.

### Local Build

To build the package locally, run:

```bash
python create_portable_comfyui.py --local
```

### CI Build

The package is also built on GitHub CI using the workflow defined in `.github/workflows/build.yml`. This workflow:

1. Runs on multiple platforms (macOS, Windows)
2. Sets up Python
3. Runs the `create_portable_comfyui.py` script with the `--ci` flag
4. Uploads the resulting zip file as an artifact
5. Creates a GitHub release with the platform-specific zip files

## GitHub Automation

The project includes automation for GitHub operations:

### create_portable_comfyui.py

The main script has been extended with options to:

- Push changes to GitHub (`--push`)
- Trigger GitHub workflows (`--trigger-workflow`)

Example usage:

```bash
python create_portable_comfyui.py --local --push --trigger-workflow
```

### github_automation.py

A dedicated script for GitHub workflow automation that:

1. Triggers a workflow run
2. Monitors the workflow status
3. Downloads the artifacts when the workflow completes

Example usage:

```bash
python github_automation.py --workflow build.yml --branch main --output-dir ./artifacts
```

## Usage

To use the package:

1. Download the appropriate zip file for your platform
2. Extract it to a directory of your choice
3. Run the appropriate launch script for your platform:
   - macOS: `anymatix_comfyui_darwin`
   - Windows: `anymatix_comfyui_windows.bat`

The script will launch ComfyUI with the portable Python and the appropriate command-line arguments.

## Zip File Naming Convention

The zip files are named according to the following convention:

```
anymatix-portable-comfyui-{platform}-{architecture}-v{version}.zip
```

For example:
- `anymatix-portable-comfyui-darwin-arm64-v1.0.0.zip` for macOS on Apple Silicon
- `anymatix-portable-comfyui-windows-x64-v1.0.0.zip` for Windows on x64

## Future Improvements

- Add more custom node repositories
- Improve error handling in the build script
- Add a GUI launcher
- Add automated testing of the built packages 