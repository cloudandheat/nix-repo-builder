#!/usr/bin/env python3

import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import pygit2
import logging
import re

errors = 0

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

STATE_DIR = os.environ.get("STATE_DIR", None)
NIX_CACHE_PRIVATE_KEY_FILE = os.environ.get("NIX_CACHE_PRIVATE_KEY_FILE", None)
NIX_CACHE_UPLOAD_URI = os.environ.get("NIX_CACHE_UPLOAD_URI", None)
REF_REGEX = os.environ.get("REF_REGEX", None)

try:
    REPO_URL = os.environ["REPO_URL"]
except KeyError:
    logger.error("REPO_URL not set")
    exit(1)

TARGET_PACKAGES = os.environ.get("TARGET_PACKAGES", "").split()

try:
    TARGET_PACKAGE = os.environ["TARGET_PACKAGE"]
except KeyError:
    pass
else:
    TARGET_PACKAGES.append(TARGET_PACKAGE)

if len(TARGET_PACKAGES) == 0:
    logger.error("TARGET_PACKAGES not set")
    exit(1)


def signal_handler(sig, frame):
    print("Aborting.")
    exit(1)
    
def build_and_push(ref: pygit2.Reference):
    for package in TARGET_PACKAGES:
        build_and_push_package(ref, package)

def build_and_push_package(ref: pygit2.Reference, package):
    logger.info(f"Building {package} for {ref.name}...")
    try:
        out_path = subprocess.check_output(
            [
                "nix",
                "build",
                "--no-use-registries",
                "--print-out-paths",
                "--no-link",
                f"{GIT_DIR}?ref={ref.target}#{package}",
            ],
            stdin=subprocess.PIPE,
        )
    except subprocess.CalledProcessError:
        logger.warning(f"Build failed. {ref.target} will not be retried for {ref.name}")
        return

    out_path = out_path.strip()

    if NIX_CACHE_PRIVATE_KEY_FILE:
        logger.info(f"Signing packages for {ref.name}...")
        try:
            requisites = subprocess.Popen(
                ["nix-store", "--query", "--requisites", out_path],
                stdout=subprocess.PIPE,
            )

            subprocess.check_call(
                [
                    "nix",
                    "store",
                    "sign",
                    "--stdin",
                    "--key-file",
                    NIX_CACHE_PRIVATE_KEY_FILE,
                ],
                stdin=requisites.stdout,
            )

            requisites.wait()
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to sign packages for {ref.name}")
            raise
    else:
        logger.info(f"Skipping signing for {ref.name} because NIX_CACHE_PRIVATE_KEY_FILE is not provided.")

    if NIX_CACHE_UPLOAD_URI:
        logger.info(f"Uploading packages for {ref.name}...")
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
            logger.warning(f"Failed to upload packages for {ref.name}")
            raise
    else:
        logger.info(f"Skipping upload for {ref.name} because NIX_CACHE_UPLOAD_URI is not provided")


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
        logger.info(f"Cloning {REPO_URL} to {GIT_DIR}")
        repo = pygit2.clone_repository(REPO_URL, GIT_DIR)

        refs = (
            r.resolve()
            for r in repo.references.iterator()
            if (REF_REGEX and re.search(REF_REGEX, r.name))
        )
        for ref in refs:
            if STATE_DIR == None:
                try:
                    build_and_push(ref)
                except subprocess.CalledProcessError:
                    errors += 1
            else:
                stateful_build_and_push(ref)

    logger.info(f"Encountered {errors} errors")
    exit(errors != 0)
