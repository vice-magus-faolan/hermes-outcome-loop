#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only construction preflight. Unknown peaks forbid image acquisition/build.

Peak evidence is a reviewed operator input, not manufactured by this helper.
Resource flags and image size are not aggregate construction quotas.
"""
import argparse
import json
from pathlib import Path
import shutil

from docker_acceptance import HERMES_SHA, command, require_budget

BASE = "sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056"


def aggregate_stores(paths, peaks):
    """Several stores on one filesystem consume a single shared reserve."""
    groups = {}
    for name, path in paths.items():
        path = path.resolve(strict=True)
        device = path.stat().st_dev
        group = groups.setdefault(device, {"available": shutil.disk_usage(path).free, "peak": 0, "stores": []})
        group["stores"].append(name)
        peak = peaks.get(name)
        if type(peak) is not int or peak <= 0:
            raise RuntimeError(f"construction peak unknown: {name}")
        group["peak"] += peak
    for group in groups.values():
        require_budget(group["available"], group["peak"])
    return list(groups.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, default=Path("docker/build-budget.json"))
    parser.add_argument("--containerd-root", type=Path, required=True,
                        help="operator/runner-discovered active containerd data root, not DockerRootDir")
    args = parser.parse_args()
    inputs = json.loads(args.budget.read_text())
    if inputs["hermes_sha"] != HERMES_SHA or inputs["base_image_digest"] != BASE:
        raise RuntimeError("construction budget does not cover the candidate pins")
    info = json.loads(command(["docker", "info", "--format", "{{json .}}"] ))
    paths = {"docker": Path(info["DockerRootDir"]), "containerd": args.containerd_root,
             "workspace": Path.cwd()}
    print(json.dumps({"persistent_stores": {name: {"path": str(path),
                      "available_bytes": shutil.disk_usage(path).free} for name, path in paths.items()}}, sort_keys=True))
    if not inputs.get("measurement_evidence"):
        raise RuntimeError("construction peaks unknown; reviewed measurement/quota evidence required")
    groups = aggregate_stores(paths, inputs["incremental_peak_bytes"])
    print(json.dumps({"admitted_filesystem_groups": groups}, sort_keys=True))


if __name__ == "__main__":
    main()
