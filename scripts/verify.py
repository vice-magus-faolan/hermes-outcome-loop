#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run repository checks; fail if discovery yields no tests or Phase 0 is no-go.

Phase-0 integration requires HERMES_PHASE0_SOURCE and HERMES_PHASE0_PYTHON
(an already provisioned Hermes dependency venv). Missing prerequisites and
unsupported required interfaces fail, never skip. This is not plugin acceptance.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Validate tracked source shapes and run the repository unittest suite."""
    for directory in ("scripts", "tests", "src", "plugin", "hermes_outcome_loop"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in sorted((ROOT / "schemas").rglob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    count = suite.countTestCases()
    if count == 0:
        print("ERROR: no tests discovered", file=sys.stderr)
        return 1
    print(f"Repository verification: {count} discovered tests", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
