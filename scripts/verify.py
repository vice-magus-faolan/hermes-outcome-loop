#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run repository checks; fail if discovery yields no tests or Phase 0 is no-go.

Phase-0 integration requires HERMES_PHASE0_SOURCE and HERMES_PHASE0_PYTHON
(an already provisioned Hermes dependency venv). Missing prerequisites and
unsupported required interfaces fail, never skip. Schema/production unit checks
require requirements-dev.txt in a repo-local environment. Production real-native
integration remains a separate required downstream gate, not a Phase-0 claim.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # Source package discovery without installing into Hermes.


def test_ids(suite):
    """Flatten discovery without running tests or treating a failed import as coverage."""
    if isinstance(suite, unittest.TestSuite):
        return {identifier for child in suite for identifier in test_ids(child)}
    return {suite.id()}


def require_production_gates(identifiers: set[str]) -> None:
    """Every ADR boundary needs named executable production unit/architecture tests."""
    mapping = json.loads((ROOT / "tests/fixtures/outcome/production-map.json").read_text())
    policy = json.loads((ROOT / "schemas/protocol.json").read_text())
    if set(mapping) != set(policy["acceptance_boundaries"]):
        raise RuntimeError("incomplete production acceptance map")
    for boundary, required in mapping.items():
        if not required or not set(required) <= identifiers:
            raise RuntimeError(f"missing production acceptance tests: {boundary}")


def main() -> int:
    """Validate tracked source shapes and run the repository unittest suite."""
    from phase0_audit import main as audit_phase0
    if audit_phase0():
        return 1
    from outcome_spec import check_schemas
    check_schemas()  # Metaschemas and closed refs, not merely JSON syntax.
    for directory in ("scripts", "tests", "src", "plugin", "hermes_outcome_loop"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in sorted((ROOT / "schemas").rglob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    require_production_gates(test_ids(suite))
    count = suite.countTestCases()
    if count == 0:
        print("ERROR: no tests discovered", file=sys.stderr)
        return 1
    print(f"Repository verification: {count} discovered tests", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
