#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a deterministic directory-plugin tarball; never install or fetch anything."""
from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "hermes-outcome-loop"
FILES = ("__init__.py", "plugin.yaml", "LICENSE", "CONTRIBUTORS.md", "README.md", "requirements.txt",
         "hermes_outcome_loop/__init__.py", "hermes_outcome_loop/adapter.py",
         "hermes_outcome_loop/history.py", "hermes_outcome_loop/records.py",
         "schemas/common.schema.json", "schemas/contract.schema.json", "schemas/observation.schema.json",
         "docs/record-protocol.md", "docs/packaging.md", "docs/threat-model.md")


def build(source: Path, output: Path) -> Path:
    """Copy an explicit source allowlist into a new output, rejecting symlinks."""
    source = source.resolve(strict=True)
    output = output.absolute()
    # Validate every input before creating any partial artifact.
    for name in FILES:
        path = source / name
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError("distribution input must be a regular literal file")
    output.mkdir(parents=True, exist_ok=False)
    directory = output / NAME
    for name in FILES:
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    archive = output / (NAME + "-0.1.0.tar.gz")
    with archive.open("wb") as stream, gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as tar:
            for name in sorted(FILES):
                path = directory / name
                info = tar.gettarinfo(str(path), arcname=NAME + "/" + name)
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as body:
                    tar.addfile(info, body)
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(build(ROOT, args.output))


if __name__ == "__main__":
    main()
