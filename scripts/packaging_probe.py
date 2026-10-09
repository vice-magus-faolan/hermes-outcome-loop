#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run real distribution install/admission checks in a disposable container home."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import shutil

from native_probe import ROOT, install_fixture
from phase0_probe import prerequisites, run_child


def collect(debug: bool = False) -> dict:
    from container_policy import require_container
    require_container()
    source, interpreter = prerequisites()
    base = Path(os.environ["TMPDIR"]) / "outcome-phase0-native-packaging"
    base.mkdir()  # Fixed identity must match the public PM seed; refuse collisions.
    try:
        base = base.resolve(strict=True)
        env = install_fixture(base, "phase0-a", enabled=False)
        env["PYTHONPATH"] = str(source)
        env["HERMES_PHASE0_SOURCE"] = str(source)
        env["HERMES_RUNTIME_DIR"] = str(base / "host-home/.hermes/tools")
        code, output, errors = run_child([str(interpreter), "-B", str(ROOT / "scripts/packaging_runtime.py"),
                                         str(source), str(base)], base, env, timeout=600)
        if code:
            if debug:
                print(errors[-8192:].replace(str(base), "<disposable-root>")
                      .replace(str(source), "<hermes-source>"), file=sys.stderr)
            raise RuntimeError("supported native packaging failed; no acceptance receipt")
        return json.loads(output)
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    print(json.dumps(collect(debug=True), sort_keys=True))
