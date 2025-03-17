In this folder, please create a method to create a portable, .zip file that uncompressed to a directory named anymatix. This directory will have two subdirectories:

1) a fully self-contained python installation, portable, for macos, windows and linux (but later, when I will change these instructions). The installation will contain the packages listed in requirements.txt. 

2) a clone of the repository https://github.com/comfyanonymous/ComfyUI

3) in the subdirectory ComfyUI/custom_nodes, clones of the repos listed in repos.json

4) a anymatix_comfyui_macos script, that independently from where called, will change directory to the comfyui one, and launch the portable python on main.py, with arguments: 

        "--enable-cors-header",
        "*",
        "--force-fp16",
        "--preview-method=none",
        "--port="""
        + port
        + "8188"

The port can be the optional first argument of the launch script and default to 8188

5) all of this must be created on github CI, and optionally on the local system. First be sure it works on the local system then take full github powers to upload to CI and run (ask for keys if necessary, instruct me on how to do this)

6) first of all, initialize a github repo in this dir, and be absolutely careful to keep the generated dirs in a .gitignore from the start. The versioned files are those that are now in the repository plus anything else that you need to add

7) use whatever you prefer to implement this script (python itself, node, bash, whatever) as soon as it will run here locally, and on github CI

8) use whatever you prefer to create the portable python environment, build from source, miniforge, whatever, as soon as the license admits free redistribution accompaining (but not compiled inside) commercial projects. I made an earlier attempt to create this using miniforge but failed miserably after several iterations. Keep it simple. 

9) document your efforts in a new file called IMPLEMENTATION.md in a way that you could use to rebuild this effort from scratch if started in a new conversation. 

10) feel free to commit changes on github with clear commit messages.

11) if anything is ambiguous or underspecified do ask for clarification

12) don't launch commands that could block interactively in the terminal or if you do remember that I need to act

13) provide a concise implementation plan, let's discuss it, and start working after I approve the plan

14) always use a web search if you are unsure or your knowledge cutoff is too old

15) automatize all the steps that you can including pushing this repo (folder name is appropriate) to github in my place and if you can use github command line to launch workflow and retrieve logs and assets for testing yourself, ask for a github key if you need it and provide a link to fetch the key

16) for macOS, ensure the Python environment is optimized for Apple Silicon (M1/M2/M3) by using appropriate versions of NumPy (with Accelerate framework) and PyTorch (with MPS support) to maximize performance on these platforms

17) the zip file name must contain the architecture and version number. 

18) The version number should be taken from a file named VERSION.txt, initially containing a suitable version number for an initial release, using semantic versioning.  

19) The workflow should create a GitHub release with the version number from VERSION.txt and upload the platform-specific zip files as separate assets of this single release.  

20) The launch script should be named anymatix_comfyui (same on all platforms)