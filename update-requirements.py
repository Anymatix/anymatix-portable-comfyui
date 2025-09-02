#!/usr/bin/env python3
"""
update-requirements

Purpose:
- Fetch requirements.txt from the pinned ComfyUI commit and ALL custom node repositories listed in repos.json.
- For each repo: use the pinned commit from PIN.json when available; otherwise try main/master branch.
- Merge them (ComfyUI first, then custom nodes), de-duplicating by package name.
- Write the merged result to this repo's requirements.txt so CI builds pick it up.

Notes:
- We trust upstream ComfyUI and anymatix-comfy-nodes (and other listed nodes) requirement definitions.
- If a package appears in multiple files with different specs, we keep the first occurrence (ComfyUI takes precedence, then nodes in listed order).
- The repository list comes from repos.json; PIN.json provides commit pins for reproducibility when present.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Optional

ROOT = os.path.dirname(__file__)
PIN_PATH = os.path.join(ROOT, "PIN.json")
REPOS_PATH = os.path.join(ROOT, "repos.json")
REQ_OUT_PATH = os.path.join(ROOT, "requirements.txt")
REQ_FALLBACK_PATH = os.path.join(ROOT, "requirements-fallback.txt")

COMFY_REPO = "https://github.com/comfyanonymous/ComfyUI"
ANYMATIX_NODES_CANON_URL = "https://github.com/anymatix/anymatix-comfy-nodes.git"


def log(msg: str) -> None:
    print(f"[update-requirements] {msg}")


def read_pins() -> list:
    if not os.path.exists(PIN_PATH):
        raise RuntimeError(f"PIN.json not found at {PIN_PATH}")
    with open(PIN_PATH, "r") as f:
        return json.load(f)


def read_repos() -> List[Dict[str, str]]:
    if not os.path.exists(REPOS_PATH):
        raise RuntimeError(f"repos.json not found at {REPOS_PATH}")
    with open(REPOS_PATH, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise RuntimeError("repos.json must be a JSON array of {url}")
    return data


def get_latest_anymatix_version(pins: list) -> str:
    versions = [p.get("anymatix_version", "") for p in pins if p.get("anymatix_version")]
    if not versions:
        raise RuntimeError("No anymatix_version found in PIN.json")
    return sorted(versions)[-1]


def normalize_repo_url(url: str) -> str:
    # Lowercase owner/repo, ensure .git suffix, strip trailing slashes
    if not url:
        return url
    url = url.strip().rstrip("/")
    if not url.endswith(".git"):
        url = url + ".git"
    # normalize casing for host + owner/repo
    try:
        prefix, rest = url.split("github.com/", 1)
        # Remove trailing .git for normalization of the owner/repo part
        if rest.endswith(".git"):
            rest = rest[:-4]
        return prefix + "github.com/" + rest.lower() + ".git"
    except ValueError:
        # Fallback: lowercase everything
        if not url.endswith(".git"):
            url = url + ".git"
        return url.lower()


def build_pin_commit_map(pins: list, version: str) -> Tuple[str, Dict[str, str]]:
    """Return (comfy_commit, {normalized_repo_url: commit})."""
    comfy_commit: Optional[str] = None
    node_commits: Dict[str, str] = {}

    for pin in pins:
        if str(pin.get("anymatix_version", "")).strip() != version:
            continue
        comfy_commit = pin.get("comfyui_commit")
        for node in pin.get("custom_nodes", []):
            url = normalize_repo_url(node.get("url", ""))
            commit = node.get("commit")
            if url and commit:
                node_commits[url] = commit
        break

    if not comfy_commit:
        raise RuntimeError(f"No comfyui_commit found in PIN.json for version {version}")

    return comfy_commit, node_commits


def fetch_raw_requirements(repo: str, ref: str, path: str = "requirements.txt") -> str:
    """Fetch raw file from GitHub at specific commit."""
    # repo like https://github.com/owner/repo
    if repo.endswith(".git"):
        repo = repo[:-4]
    raw_url = repo.replace("https://github.com/", "https://raw.githubusercontent.com/")
    url = f"{raw_url}/{ref}/{path}"
    log(f"Fetching {url}")
    with urllib.request.urlopen(url) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return resp.read().decode("utf-8")


def try_fetch_requirements_with_fallback(repo: str, ref_or_commit: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Try to fetch requirements.txt using the provided ref/commit; if None or 404, try 'main' then 'master'.
    Returns (requirements_text or None, used_ref)."""
    # Order: provided -> main -> master
    attempts = []
    if ref_or_commit:
        attempts.append(ref_or_commit)
    attempts.extend(["main", "master"])
    last_err: Optional[Exception] = None
    for ref in attempts:
        try:
            txt = fetch_raw_requirements(repo, ref, "requirements.txt")
            return txt, ref
        except Exception as e:
            last_err = e
            continue
    log(f"No requirements.txt found for {repo}: {last_err}")
    return None, None


def assemble_repo_urls(repos: List[Dict[str, str]], node_pin_map: Dict[str, str]) -> List[str]:
    """Return a de-duplicated, normalized list of repo URLs from repos.json and PIN.json."""
    urls: Dict[str, bool] = {}
    # From repos.json
    for entry in repos:
        url = normalize_repo_url(entry.get("url", "").strip())
        if url:
            urls[url] = True
    # From PIN.json custom_nodes
    for url in node_pin_map.keys():
        urls[normalize_repo_url(url)] = True
    # Skip ComfyUI if present
    urls.pop(normalize_repo_url(COMFY_REPO + ".git"), None)
    return list(urls.keys())


def parse_requirements(text: str) -> List[str]:
    lines: List[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        lines.append(s)
    return lines


def req_key(line: str) -> str:
    """Crude key extractor: package name up to first version/operator char, lowercased.
    Handles extras like pkg[foo]."""
    ops = ["==", ">=", "<=", "~=", ">", "<", "!=" , "==="]
    idx = len(line)
    for op in ops:
        p = line.find(op)
        if p != -1:
            idx = min(idx, p)
    # also split on whitespace to handle markers
    base = line[:idx].strip().split()[0]
    return base.lower()


def merge_requirements(primary: List[str], secondary: List[str]) -> List[str]:
    out: List[str] = []
    seen: Dict[str, str] = {}
    for src in (primary, secondary):
        for line in src:
            key = req_key(line)
            if key in seen:
                continue
            seen[key] = line
            out.append(line)
    return out


def read_fallback_requirements(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return parse_requirements(f.read())


def sort_requirements(lines: List[str]) -> List[str]:
    """Sort requirements alphabetically by package key, case-insensitive, stable by full line."""
    return sorted(lines, key=lambda s: (req_key(s), s.lower()))


def main() -> int:
    print("\n=== update-requirements ===")
    print("Fetch requirements from pinned ComfyUI and ALL repos in repos.json (pinned when available), merge, and write to requirements.txt for CI.")

    try:
        pins = read_pins()
        repos = read_repos()
        version = get_latest_anymatix_version(pins)
        comfy_commit, node_pin_map = build_pin_commit_map(pins, version)

        print(f"Pinned anymatix_version: {version}")
        print(f"ComfyUI commit: {comfy_commit}")

        # 1) ComfyUI first
        comfy_req_txt = fetch_raw_requirements(COMFY_REPO, comfy_commit, "requirements.txt")
        comfy_reqs = parse_requirements(comfy_req_txt)

        # 2) Custom nodes from repos.json + PIN.json (union)
        merged = list(comfy_reqs)
        used_sources: List[Tuple[str, str, str]] = [(COMFY_REPO, comfy_commit, "pinned")]  # (repo_url, ref, mode)

        all_urls = assemble_repo_urls(repos, node_pin_map)
        for url in all_urls:
            # Skip ComfyUI just in case
            if url.endswith("/comfyanonymous/comfyui.git"):
                continue

            ref = node_pin_map.get(url)
            txt, used_ref = try_fetch_requirements_with_fallback(url, ref)
            mode = "pinned" if ref else (used_ref or "skipped")
            if txt:
                node_reqs = parse_requirements(txt)
                merged = merge_requirements(merged, node_reqs)
                used_sources.append((url, used_ref or (ref or "unknown"), "pinned" if ref else "branch"))
            else:
                used_sources.append((url, used_ref or (ref or "n/a"), "missing"))

        # 3) Ensure fallback packages are present: allow upstream bumps, but keep any missing ones
        fallback = read_fallback_requirements(REQ_FALLBACK_PATH)
        if fallback:
            merged_keys = {req_key(line) for line in merged}
            for line in fallback:
                if req_key(line) not in merged_keys:
                    merged.append(line)
                    merged_keys.add(req_key(line))

        # 4) Sort alphabetically for stable, readable diffs
        merged = sort_requirements(merged)

        # Build header (no comments)
        header = []
        out_text = "\n".join(header + merged) + "\n"

        with open(REQ_OUT_PATH, "w", encoding="utf-8") as f:
            f.write(out_text)
        print(f"Wrote merged requirements to {REQ_OUT_PATH} ({len(merged)} entries)")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
