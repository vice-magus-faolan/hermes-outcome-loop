#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public-only Docker BUILD provisioning, never a host preparer or live installer.

The Docker construction budget must already be admitted by the operator/runner.
This script is not called by acceptance. PM builds a fresh dependency closure;
no immutable environment is patched with pip and no source lock is modified.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

HERMES_SHA = "f42f579cf8bac4918ac9599bece71618afadd846"
HERMES_URL = "https://github.com/vice-magus-faolan/hermes-agent.git"


def run(command, env):
    subprocess.run(command, env=env, cwd="/provision", check=True, timeout=1200)


def main():
    if os.environ.get("OUTCOME_DOCKER_PROVISION") != HERMES_SHA or Path.home() != Path("/provision") or sys.version_info[:2] != (3, 14):
        raise RuntimeError("provision only inside the pinned Docker build environment")
    if sys.argv[1:] == ["--inventory"]:
        values = sorted((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions())
        Path("/opt/dependencies.json").write_text(json.dumps(values), encoding="utf-8")
        return
    root = Path("/provision")
    root.mkdir(exist_ok=True)
    (root / "tmp").mkdir()
    source = Path("/opt/hermes")
    env = {"PATH": os.environ["PATH"], "HOME": str(root), "HERMES_HOME": str(root / "home"),
           "TMPDIR": str(root / "tmp"), "PYTHONDONTWRITEBYTECODE": "1",
           "HERMES_DISABLE_LAZY_INSTALLS": "true"}
    run(["git", "init", str(source)], env)
    run(["git", "-C", str(source), "fetch", "--depth", "1", HERMES_URL, HERMES_SHA], env)
    run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], env)
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if sha != HERMES_SHA:
        raise RuntimeError("public source pin mismatch")
    env["PYTHONPATH"] = str(source)
    exported = root / "core-requirements.txt"
    common = [sys.executable, "-B", "-m", "pm.build_env"]
    run(common + ["--source", str(source), "--export-requirements", str(exported),
                  "--cache", str(root / "cache")], env)
    combined = root / "runtime-requirements.txt"
    combined.write_text(exported.read_text() + "\n" + (root / "requirements.txt").read_text(), encoding="utf-8")
    run(common + ["--requirements", str(combined), "--out", "/opt/runtime",
                  "--cache", str(root / "cache")], env)
    env["OUTCOME_DOCKER_PROVISION"] = HERMES_SHA
    run(["/opt/runtime/bin/python", "-B", "/provision/provision_docker.py", "--inventory"], env)
    run(["git", "-C", str(source), "diff", "--exit-code", "HEAD"], env)
    receipt = {"hermes_sha": sha, "python": sys.version.split()[0],
               "lock_sha256": hashlib.sha256((source / "uv.lock").read_bytes()).hexdigest(),
               "requirements_sha256": hashlib.sha256(combined.read_bytes()).hexdigest()}
    Path("/opt/provision-receipt.json").write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    # Read-only container Git inspection needs this build-owned path to be trusted.
    run(["git", "config", "--system", "--add", "safe.directory", str(source)], env)


if __name__ == "__main__":
    main()
