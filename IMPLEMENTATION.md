# Implementation Details

Technical reference for maintainers of the portable ComfyUI bundle.

## Components

1. Miniforge-based portable Python (installed under `anymatix/python`)
2. Upstream ComfyUI checkout (`anymatix/ComfyUI`)
3. Custom node repositories (`anymatix/ComfyUI/custom_nodes/*` from `repos.json`)
4. Platform launch scripts (`anymatix_comfyui` or `anymatix_comfyui.bat`)
5. Packaging logic producing a versioned zip

Currently macOS & Windows builds are active in CI; Linux logic is present but workflow job is commented out.

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

Cloned from `https://github.com/comfyanonymous/ComfyUI.git` without pinning by default (HEAD of default branch). For deterministic builds insert a checkout line after clone:

```python
run_command(["git", "clone", COMFYUI_REPO, COMFYUI_DIR])
run_command(["git", "-C", COMFYUI_DIR, "checkout", "<commit-sha>"])
```

Record the chosen commit in release notes if you keep floating HEAD.

### Custom Node Repositories

List defined in `repos.json` (array of objects with at least `url`). All repos are cloned directly into `custom_nodes/`. Optional future enhancement: extend each entry with an optional `commit` key and perform a checkout to pin versions (ensures reproducibility). For now they float at remote HEAD.

### Launch Scripts

Created inside the `anymatix/` directory. Both variants accept an optional first argument = port (default 8188). Flags presently used:
- `--enable-cors-header "*"`
- `--force-fp16`
- `--preview-method=none`

Adjust flags cautiously; changes impact performance / compatibility.

#### macOS Quarantine Handling

On macOS, downloaded applications are marked with a quarantine attribute (`com.apple.quarantine`) as a security measure. This can prevent the portable ComfyUI package from running properly. The macOS launch script includes logic to:

1. Check if the quarantine attribute exists on the package directory
2. If found, attempt to remove it using the `xattr` command
3. Provide clear instructions if manual removal is needed

This approach ensures that the quarantine attribute is only removed when necessary, avoiding unnecessary operations on subsequent launches.

### Version Management

`VERSION.txt` supplies the version token embedded in zip filenames and used by the release workflow. No environment override currently inside `create_portable_comfyui.py`; workflow reads the file directly.

External host projects may synchronize their version by updating this file before invoking the workflow. Keep SemVer (pre-release tags allowed). Zip naming formula:

```
anymatix-portable-comfyui-{system}-{arch}-v{version}.zip
```

## Build Script Flow (`create_portable_comfyui.py`)

1. Ensure `anymatix/` base directory exists
2. Download & install Miniforge to `anymatix/python`
3. Install Python 3.10 + requirements (with Apple Silicon optimizations: Accelerate BLAS pin + torch MPS)
4. Clone ComfyUI
5. Clone custom nodes
6. Generate launch script(s)
7. Package directory tree into a versioned zip
8. (Optional) push / trigger workflow if flags supplied

### Local Build

To build the package locally, run:

```bash
python create_portable_comfyui.py --local
```

### CI Build

Workflow (`.github/workflows/build.yml`):
1. Parallel jobs build macOS & Windows artifacts
2. Each job runs `python create_portable_comfyui.py --ci`
3. Artifacts uploaded using generated filenames
4. Release job reads `VERSION.txt`, downloads artifacts, publishes release & tag `v<VERSION>`
5. Linux job is disabled (can be re-enabled by uncommenting block)

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
   - macOS/Linux: `anymatix_comfyui`
   - Windows: `anymatix_comfyui.bat`

The script will launch ComfyUI with the portable Python and the appropriate command-line arguments.

## Reproducibility Enhancements (Roadmap)

Short term:
- Add optional commit pinning for ComfyUI & each custom node
- Provide a manifest file listing all repo URLs + resolved SHAs + Python packages

Medium term:
- Hash the `anymatix/` directory content and store a build metadata JSON alongside the zip
- Allow environment variable override for version (kept out for now to avoid accidental mismatches)

## Future Improvements

- Commit pinning support in `repos.json` (schema: `{ "url": "...", "commit": "..." }`)
- Automated test workflow that launches the built bundle headless and runs a sample graph
- Optional Linux build re-enable
- Integrity manifest & signature
- GUI launcher / platform integration wrappers