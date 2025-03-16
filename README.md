# Anymatix Portable ComfyUI

A portable, self-contained distribution of ComfyUI for macOS.

## Overview

This project creates a portable ComfyUI package that includes:

1. A fully self-contained Python installation with all required dependencies
2. The ComfyUI repository
3. Custom node repositories
4. A launch script

## Usage

1. Download the latest release from the [Releases](https://github.com/your-username/anymatix-portable-comfyui/releases) page
2. Extract the zip file to a directory of your choice
3. Run the `anymatix_comfyui_macos` script

## Building from Source

To build the package from source:

1. Clone this repository
2. Run `python create_portable_comfyui.py --local`

## Requirements

The package includes all required dependencies, but to build it, you need:

- Python 3.10 or later
- Git

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The core ComfyUI application
- [Miniforge](https://github.com/conda-forge/miniforge) - The conda distribution used for the portable Python environment 