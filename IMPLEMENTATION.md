# Anymatix Portable ComfyUI Implementation

This document describes the implementation of the Anymatix Portable ComfyUI package.

## Overview

The Anymatix Portable ComfyUI package is a self-contained, portable distribution of ComfyUI that includes:

1. A portable Python environment with all required dependencies
2. The ComfyUI repository
3. Custom node repositories
4. A launch script

The package is designed to be platform-independent and can be run on macOS, Windows, and Linux.

## Implementation Details

### Portable Python Environment

The portable Python environment is created using Miniforge, a minimal installer for conda. Miniforge is chosen because:

- It's lightweight compared to Anaconda
- It uses conda-forge as the default channel, which has a wide range of packages
- It's available for all major platforms (macOS, Windows, Linux)
- It has a permissive license that allows for redistribution

The Python environment includes all the packages listed in `requirements.txt`.

### ComfyUI Repository

The ComfyUI repository is cloned from https://github.com/comfyanonymous/ComfyUI.git. This repository contains the core ComfyUI application.

### Custom Node Repositories

Custom node repositories are cloned from the URLs specified in `repos.json`. These repositories contain additional nodes that extend the functionality of ComfyUI.

### Launch Script

A launch script is created for macOS that:

1. Changes to the ComfyUI directory
2. Launches ComfyUI with the portable Python
3. Passes the appropriate command-line arguments

The launch script accepts an optional port number as the first argument, defaulting to 8188 if not provided.

## Building the Package

The package is built using the `create_portable_comfyui.py` script. This script:

1. Creates the portable Python environment
2. Clones the ComfyUI repository
3. Clones the custom node repositories
4. Creates the launch script
5. Packages everything into a zip file

The script can be run locally or on GitHub CI.

### Local Build

To build the package locally, run:

```bash
python create_portable_comfyui.py --local
```

### CI Build

The package is also built on GitHub CI using the workflow defined in `.github/workflows/build.yml`. This workflow:

1. Runs on macOS
2. Sets up Python
3. Runs the `create_portable_comfyui.py` script with the `--ci` flag
4. Uploads the resulting zip file as an artifact

## Usage

To use the package:

1. Download the zip file
2. Extract it to a directory of your choice
3. Run the `anymatix_comfyui_macos` script

The script will launch ComfyUI with the portable Python and the appropriate command-line arguments.

## Future Improvements

- Add support for Windows and Linux launch scripts
- Add more custom node repositories
- Improve error handling in the build script
- Add a GUI launcher 