#!/usr/bin/env python3
"""
PyInstaller approach for creating a single executable or bundled app.
Results in ~100-300MB depending on included libraries.
"""

import subprocess
import os

def create_pyinstaller_bundle():
    """Create a bundled executable using PyInstaller."""
    
    # Create a main ComfyUI launcher script
    main_script = """
import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run ComfyUI
if __name__ == "__main__":
    import comfyui.main
    comfyui.main.main()
"""
    
    with open("comfyui_launcher.py", "w") as f:
        f.write(main_script)
    
    # PyInstaller command with optimizations
    pyinstaller_cmd = [
        "pyinstaller",
        "--onedir",                    # Bundle in directory (easier to customize)
        "--windowed",                  # No console window (Windows)
        "--optimize", "2",             # Maximum Python optimization
        "--strip",                     # Strip debug symbols
        "--noupx",                     # Don't use UPX compression (causes issues)
        "--exclude-module", "tkinter", # Exclude unnecessary modules
        "--exclude-module", "unittest",
        "--exclude-module", "doctest", 
        "--exclude-module", "pdb",
        "--hidden-import", "torch",    # Ensure PyTorch is included
        "--hidden-import", "torchvision",
        "--hidden-import", "torchaudio",
        "--hidden-import", "torchsde",
        "--add-data", "ComfyUI;ComfyUI",  # Include ComfyUI files
        "comfyui_launcher.py"
    ]
    
    print("Creating PyInstaller bundle...")
    subprocess.run(pyinstaller_cmd, check=True)
    print("PyInstaller bundle created in dist/")

if __name__ == "__main__":
    create_pyinstaller_bundle()
