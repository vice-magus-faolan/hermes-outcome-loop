#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check accessible construction backing mounts for the operational reserve.

Confirm Docker/containerd routing read-only before selecting mounts. This check
does not predict build peaks, enforce a disk quota or guarantee that a build fits.
"""
import argparse
import json
from pathlib import Path
import shutil

from docker_acceptance import command, require_reserve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, action="append",
                        help="accessible actual backing mount; repeat for separate stores")
    args = parser.parse_args()
    info = json.loads(command(["docker", "info", "--format", "{{json .}}"] ))
    paths = args.store or [Path(info["DockerRootDir"]), Path.cwd()]
    stores = []
    for path in paths:
        available = shutil.disk_usage(path).free
        require_reserve(available)
        stores.append({"path": str(path), "available_bytes": available})
    print(json.dumps({"persistent_stores": stores, "build_peak_bytes": None}, sort_keys=True))


if __name__ == "__main__":
    main()
