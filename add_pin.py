#!/usr/bin/env python3
"""
Add a (anymatix_version, comfyui_commit, custom_nodes) pin to PIN.json if not already present.
- Reads version from ../../app/VERSION.txt
- Reads current commit hash from anymatix/ComfyUI (local clone)
- Reads repos.json and gets commit hash for each custom node repo in anymatix/ComfyUI/custom_nodes
- Adds to PIN.json only if not already present
"""
import os
import json
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_VERSION_PATH = os.path.abspath(os.path.join(REPO_ROOT, '../../app/VERSION.txt'))
COMFYUI_PATH = os.path.join(REPO_ROOT, 'anymatix', 'ComfyUI')
CUSTOM_NODES_PATH = os.path.join(COMFYUI_PATH, 'custom_nodes')
REPOS_JSON_PATH = os.path.join(REPO_ROOT, 'repos.json')
PIN_PATH = os.path.join(REPO_ROOT, 'PIN.json')

def get_anymatix_version():
    with open(APP_VERSION_PATH, 'r') as f:
        return f.read().strip()

def get_comfyui_commit():
    try:
        return subprocess.check_output(
            ['git', '-C', COMFYUI_PATH, 'rev-parse', 'HEAD'],
            text=True
        ).strip()
    except subprocess.CalledProcessError:
        raise RuntimeError(f"Could not get commit hash from {COMFYUI_PATH}")

def get_custom_nodes_commits():
    with open(REPOS_JSON_PATH, 'r') as f:
        repos = json.load(f)
    pins = []
    for repo in repos:
        url = repo['url']
        name = os.path.splitext(os.path.basename(url))[0]
        node_path = os.path.join(CUSTOM_NODES_PATH, name)
        try:
            commit = subprocess.check_output(
                ['git', '-C', node_path, 'rev-parse', 'HEAD'],
                text=True
            ).strip()
        except subprocess.CalledProcessError:
            commit = None
        pins.append({'url': url, 'commit': commit})
    return pins

def add_pin():
    version = get_anymatix_version()
    commit = get_comfyui_commit()
    custom_nodes = get_custom_nodes_commits()
    if os.path.exists(PIN_PATH):
        with open(PIN_PATH, 'r') as f:
            pins = json.load(f)
    else:
        pins = []
    for pin in pins:
        if (
            pin.get('anymatix_version') == version and
            pin.get('comfyui_commit') == commit and
            pin.get('custom_nodes') == custom_nodes
        ):
            print(f"Pin already present: version={version}, commit={commit}")
            return
    pins.append({'anymatix_version': version, 'comfyui_commit': commit, 'custom_nodes': custom_nodes})
    with open(PIN_PATH, 'w') as f:
        json.dump(pins, f, indent=4)
    print(f"Added pin: version={version}, commit={commit}, custom_nodes={custom_nodes}")

if __name__ == '__main__':
    add_pin()
