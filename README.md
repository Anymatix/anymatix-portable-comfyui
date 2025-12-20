# Portable ComfyUI Bundle

Self‑contained ComfyUI distribution for macOS and Windows (Linux support is easy to re‑enable). Produces a zip that runs without touching an existing Python install.

## What You Get
1. Miniforge based portable Python (Python 3.10) with required packages
2. A fresh clone of upstream ComfyUI
3. Custom node repositories (from `repos.json`)
4. Platform launch scripts (`anymatix_comfyui` / `anymatix_comfyui.bat`)
5. Versioned archive: `anymatix-portable-comfyui-{system}-{arch}-v<VERSION>.zip`

## Quick Use (End Users)
1. Download a release zip from the [Releases](https://github.com/vincenzoml/anymatix-portable-comfyui/releases) page
2. Extract anywhere you have write permissions
3. Run:
   - macOS / Linux: `./anymatix/anymatix_comfyui [port]`
   - Windows: `anymatix\anymatix_comfyui.bat [port]`
   (Port optional, defaults to 8188)

### Performance Notes
- **Apple Silicon Macs (M1/M2/M3+)**: Fully optimized with native ARM64 code, Apple Accelerate framework for fast NumPy operations, and Metal GPU acceleration
- **Windows with NVIDIA GPU**: Includes CUDA 12.4 support for GPU acceleration  
- **All Platforms**: Uses Python 3.10 with optimized scientific computing stack

### macOS Quarantine Note
The script attempts to remove the quarantine attribute automatically. If you still get a security warning:
```bash
xattr -r -d com.apple.quarantine /path/to/unzipped/anymatix
```

## Building Locally (Developers)
Prereqs: Python 3.10+, Git, unzip utilities.

```bash
python -m pip install --upgrade pip
python create_portable_comfyui.py --local
```
Resulting zip appears in the repo root.

Flags:
- `--local` (no CI assumptions)
- `--ci` (used in GitHub Actions; keeps produced filename as generated)
- `--push` (commit & push artifacts/changes) – use cautiously
- `--trigger-workflow` with `--workflow build.yml` (uses GitHub CLI `gh` if configured)

## Updating to Latest ComfyUI
By default the script clones the HEAD of upstream main. To explicitly pin / update:
1. Build once, then record the commit:
   ```bash
   (cd anymatix/ComfyUI && git rev-parse HEAD)
   ```
2. To pin a specific commit, edit `create_portable_comfyui.py` inside `clone_comfyui()` after the clone step:
   ```python
   run_command(["git", "clone", COMFYUI_REPO, COMFYUI_DIR])
   run_command(["git", "-C", COMFYUI_DIR, "checkout", "<commit-sha>"])
   ```
3. Rebuild and test launch.
4. Commit with message e.g. `chore: update ComfyUI to <short-sha>`.

Validation checklist after updating:
- Launch works (UI reachable)
- Basic workflow executes
- Custom nodes load without ImportError
- Python version still 3.10 (expected)

## Custom Nodes
Repositories listed in `repos.json` are cloned into `anymatix/ComfyUI/custom_nodes/`.

To add one:
1. Append an object with a `url` field to `repos.json`
2. Re-run build
3. Verify nodes appear in the UI

For reproducibility, prefer referencing stable commits in those repos (fork & pin if upstream is volatile).

## Reproducibility & Pinning
Current default = floating HEAD of upstream repos. For strict reproducibility:
- Pin ComfyUI commit (see above)
- Pin each custom node repo commit (add a checkout command after clone in a small helper or extend script)
- Optionally vendor a `requirements.txt` lock snapshot

Document the commits used in release notes if you float.

## Versioning
`VERSION.txt` holds the semantic version used in archive names and GitHub releases (ex: `1.0.0`).

If this project is used within a host application (e.g. as a submodule) you can synchronize by writing that host version into this `VERSION.txt` before triggering CI.

Semantic guidelines:
- MAJOR: packaging/build changes that alter structure or invocation
- MINOR: new included nodes / features
- PATCH: fixes, dependency pin adjustments, minor script improvements

## Version 2.0 Changes

Version 2.0 introduces a simplified architecture:

### Configuration
- **VERSION.txt**: Simple text file containing the version (e.g., `2.0.0`)
- **PIN.json**: Now optional - the Anymatix app manages commit pinning via its own PIN.json
- Version is read from `VERSION.txt` first, falling back to `PIN.json` for backward compatibility

### Requirements
- **requirements.txt**: Minimal bootstrap packages only (pygit2, yaml, aiohttp, etc.)
- ComfyUI and custom node requirements are installed at runtime by `bootstrap.py`
- GPU-specific PyTorch installation handled by bootstrap based on detected hardware

### Bootstrap Flow
1. App downloads the portable base system zip
2. App uploads `bootstrap.py` and `PIN.json` (app's version) to target directory
3. `bootstrap.py` reads `PIN.json` for commit pins and installs requirements
4. ComfyUI is cloned/updated to the pinned commit
5. Custom nodes are cloned/updated to their pinned commits

This allows the app to control exact versions while the portable bundle provides only the Python environment.

## CI Overview
GitHub Actions workflow (`.github/workflows/build.yml`) builds macOS & Windows zips then creates a release tagged `v<VERSION>` (version read from `VERSION.txt`). Linux job is present but commented out.

### Triggering Builds
Since the workflow uses `workflow_dispatch`, you can trigger builds manually:

**Option 1: GitHub Web Interface (Recommended)**
1. Go to the repository on GitHub
2. Click "Actions" tab
3. Select "Build Portable ComfyUI" workflow  
4. Click "Run workflow" → Choose branch → "Run workflow"

**Option 2: GitHub CLI**
```bash
gh workflow run build.yml
```

**Option 3: Push Changes**
The workflow can also be configured to run on pushes by uncommenting the push trigger in `build.yml`.

### Platform Optimizations
- **Apple Silicon (M1/M2/M3+)**: Native ARM64 builds with Apple Accelerate framework for NumPy, Metal Performance Shaders (MPS) support for PyTorch GPU acceleration
- **Windows**: CUDA 12.4 PyTorch installation with automatic fallback to CPU-only if CUDA unavailable
- **Cross-platform**: Miniforge-based Python 3.10 environment ensures consistent package management

## File / Naming Reference
Archive pattern: `anymatix-portable-comfyui-{system}-{arch}-v<VERSION>.zip`
Examples:
- `anymatix-portable-comfyui-darwin-arm64-v1.0.0.zip`
- `anymatix-portable-comfyui-windows-x64-v1.0.0.zip`

Launch scripts created under `anymatix/` directory inside the archive.

## Troubleshooting
| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| Missing nodes | Repo absent in `repos.json` | Add entry & rebuild |
| ImportError at launch | Dependency not installed / pin drift | Rebuild; ensure requirements satisfied |
| Wrong version in release | `VERSION.txt` not updated | Edit file, commit, rerun CI |
| macOS security block | Quarantine attribute | Remove with `xattr` as shown |

## License
MIT – see [LICENSE](LICENSE). Check upstream component licenses (ComfyUI & custom nodes) for their terms.

## Acknowledgments
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Miniforge](https://github.com/conda-forge/miniforge)

---
Contributions welcome. Keep changes small and build script readable.