# Anymatix Portable ComfyUI

A portable, self-contained distribution of ComfyUI for macOS and Windows.

## Overview

This project creates a portable ComfyUI package that includes:

1. A fully self-contained Python installation with all required dependencies
2. The ComfyUI repository
3. Custom node repositories
4. Platform-specific launch scripts

## Usage

1. Download the latest release from the [Releases](https://github.com/vincenzoml/anymatix-portable-comfyui/releases) page
2. Extract the zip file to a directory of your choice
3. Run the appropriate launch script for your platform:
   - macOS: `anymatix_comfyui_darwin`
   - Windows: `anymatix_comfyui_windows.bat`

### macOS Notes

On macOS, the launch script will automatically attempt to remove the quarantine attribute that macOS applies to downloaded files. If the automatic removal fails, you can manually remove the quarantine attribute by running:

```bash
xattr -r -d com.apple.quarantine /path/to/extracted/anymatix
```

## Building from Source

To build the package from source:

1. Clone this repository
2. Run `python create_portable_comfyui.py --local`

## Requirements

The package includes all required dependencies, but to build it, you need:

- Python 3.10 or later
- Git

## Version Information

The current version is 1.0.0, which is the first stable release. The version number follows semantic versioning:

- Major version: Significant changes that may break compatibility
- Minor version: New features that don't break compatibility
- Patch version: Bug fixes and minor improvements

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The core ComfyUI application
- [Miniforge](https://github.com/conda-forge/miniforge) - The conda distribution used for the portable Python environment 