#!/usr/bin/env python3
"""
Script to automate GitHub workflow management and artifact retrieval.
This script will:
1. Trigger a workflow run
2. Monitor the workflow status
3. Download the artifacts when the workflow completes
"""

import os
import sys
import time
import subprocess
import argparse
import json


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="GitHub Workflow Automation")
    parser.add_argument("--workflow", default="build.yml", help="Workflow file name")
    parser.add_argument(
        "--branch", default="main", help="Branch to run the workflow on"
    )
    parser.add_argument(
        "--output-dir", default="./artifacts", help="Directory to save artifacts"
    )
    return parser.parse_args()


def run_command(command):
    """Run a command and return the output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def trigger_workflow(workflow, branch):
    """Trigger a workflow run."""
    print(f"Triggering workflow {workflow} on branch {branch}...")
    run_command(f"gh workflow run {workflow} --ref {branch}")

    # Get the run ID of the workflow we just triggered
    time.sleep(2)  # Give GitHub a moment to register the workflow run
    runs = json.loads(
        run_command(
            f"gh api repos/{{owner}}/{{repo}}/actions/workflows/{workflow}/runs --jq '.workflow_runs[0]'"
        )
    )
    run_id = runs["id"]
    print(f"Workflow run ID: {run_id}")
    return run_id


def monitor_workflow(run_id):
    """Monitor the workflow status."""
    print(f"Monitoring workflow run {run_id}...")
    while True:
        status = run_command(f"gh run view {run_id} --json status --jq '.status'")
        print(f"Workflow status: {status}")

        if status in ["completed", "cancelled", "failure"]:
            conclusion = run_command(
                f"gh run view {run_id} --json conclusion --jq '.conclusion'"
            )
            print(f"Workflow conclusion: {conclusion}")
            return conclusion == "success"

        time.sleep(30)  # Check every 30 seconds


def download_artifacts(run_id, output_dir):
    """Download the artifacts from a workflow run."""
    print(f"Downloading artifacts from workflow run {run_id}...")
    os.makedirs(output_dir, exist_ok=True)
    run_command(f"gh run download {run_id} --dir {output_dir}")
    print(f"Artifacts downloaded to {output_dir}")


def main():
    """Main function."""
    args = parse_args()

    # Trigger the workflow
    run_id = trigger_workflow(args.workflow, args.branch)

    # Monitor the workflow
    success = monitor_workflow(run_id)

    if success:
        # Download the artifacts
        download_artifacts(run_id, args.output_dir)
        print("Workflow completed successfully!")
    else:
        print("Workflow failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
