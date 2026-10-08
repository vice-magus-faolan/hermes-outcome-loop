# SPDX-License-Identifier: GPL-3.0-or-later
"""Accidental host-execution fence, not a Python security sandbox."""
import os
from pathlib import Path


def require_container() -> None:
    """Heavy native checks run only on the fixed read-only container path layout."""
    if not Path("/.dockerenv").is_file() or os.getuid() != 65532:
        raise RuntimeError("native acceptance requires the non-root Docker runner")
    if Path(__file__).resolve().parents[1] != Path("/source"):
        raise RuntimeError("native acceptance source must be the staged /source mount")
    options = {line.split()[4]: line.split()[5].split(",")
               for line in Path("/proc/self/mountinfo").read_text().splitlines()}
    if "ro" not in options.get("/", []) or "ro" not in options.get("/source", []):
        raise RuntimeError("native acceptance requires read-only root and source")
