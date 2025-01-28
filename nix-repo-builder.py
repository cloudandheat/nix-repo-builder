#!/usr/bin/env python3

import os
import pathlib
import signal
import subprocess
import sys
import tempfile

import pygit2


def signal_handler(sig, frame):
    print("Aborting.")
    exit(1)


STATE_DIR = os.environ.get("STATE_DIR", None)
REPO_URL = os.environ["REPO_URL"]
TARGET_PACKAGE = os.environ["TARGET_PACKAGE"]

NIX_CACHE_PRIVATE_KEY_FILE = os.environ.get("NIX_CACHE_PRIVATE_KEY_FILE", None)
NIX_CACHE_UPLOAD_URI = os.environ.get("NIX_CACHE_UPLOAD_URI", None)


errors = 0


def build_and_push(ref: pygit2.Reference):
    print(f"INFO: Building packages for {ref.name}...")
    try:
        out_path = subprocess.check_output(
            [
                "nix",
                "build",
                "--no-use-registries",
                "--print-out-paths",
                "--no-link",
                f"{GIT_DIR}?ref={ref.target}#{TARGET_PACKAGE}",
            ],
            stdin=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        print(f"WARNING: Build failed. {ref.target} will not be retried for {ref.name}")
        return

    out_path = out_path.strip()

    if NIX_CACHE_PRIVATE_KEY_FILE:
        print(f"INFO: Signing packages for {ref.name}...")
        try:
            subprocess.check_call(
                [
                    "nix",
                    "store",
                    "sign",
                    out_path,
                    "--key-file",
                    NIX_CACHE_PRIVATE_KEY_FILE,
                ],
                stdin=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            print(f"WARNING: Failed to sign packages for {ref.name}")
            raise
    else:
        print(f"INFO: Skipping signing for {ref.name} because NIX_CACHE_PRIVATE_KEY_FILE is not provided.")

    if NIX_CACHE_UPLOAD_URI:
        print(f"INFO: Uploading packages for {ref.name}...")
        try:
            subprocess.check_call(
                [
                    "nix",
                    "copy",
                    out_path,
                    "--to",
                    NIX_CACHE_UPLOAD_URI,
                ],
                stdin=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            print(f"WARNING: Failed to upload packages for {ref.name}")
            raise
    else:
        print(f"INFO: Skipping upload for {ref.name} because NIX_CACHE_UPLOAD_URI is not provided")


def stateful_build_and_push(ref: pygit2.Reference):
    ref_path = pathlib.Path(STATE_DIR) / ref.name

    try:
        with ref_path.open("r") as fd:
            current_id = fd.read()
    except FileNotFoundError:
        pass
    else:
        if current_id == ref.target:
            return

    try:
        build_and_push(ref)
    except subprocess.CalledProcessError:
        print(f"{ref.name} will be retried")
        global errors
        errors += 1
        return

    ref_path.parent.mkdir(exist_ok=True, parents=True)
    with ref_path.open("w") as fd:
        fd.write(str(ref.target))


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    with tempfile.TemporaryDirectory() as GIT_DIR:
        print(f"INFO: Cloning {REPO_URL} to {GIT_DIR}")
        repo = pygit2.clone_repository(REPO_URL, GIT_DIR)

        for ref in (r.resolve() for r in repo.references.iterator()):
            if STATE_DIR == None:
                try:
                    build_and_push(ref)
                except subprocess.CalledProcessError:
                    errors += 1
            else:
                stateful_build_and_push(ref)

    print(f"Encountered {errors} errors")
    exit(errors != 0)
