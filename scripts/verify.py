#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run production unit, distribution and required real-Hermes tests in Docker."""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_ids(suite):
    """Flatten discovery; failed imports are not proof of coverage."""
    if isinstance(suite, unittest.TestSuite):
        return {identifier for child in suite for identifier in test_ids(child)}
    return {suite.id()}


def require_production_gates(identifiers: set[str]) -> None:
    """Keep every production boundary and the focused native/distribution checks."""
    mapping = json.loads((ROOT / "tests/fixtures/outcome/production-map.json").read_text())
    policy = json.loads((ROOT / "schemas/protocol.json").read_text())
    if set(mapping) != set(policy["acceptance_boundaries"]):
        raise RuntimeError("incomplete production acceptance map")
    required = {
        "test_native.ProductionNativeTests.test_results_retry_unfinished_and_full_native_history",
        "test_native.ProductionNativeTests.test_restart_profiles_and_actual_parallel_races",
        "test_native.ProductionNativeTests.test_fail_observationally_and_admission_readback",
        "test_native.NativeSafetyTests.test_fixture_environment_discards_live_worker_credentials",
        "test_packaging.DistributionTests.test_directory_plugin_has_closed_reproducible_distribution",
        "test_packaging.DistributionTests.test_incomplete_symlink_and_existing_output_fail_closed",
    }
    for boundary, gates in {**mapping, "native_and_distribution": sorted(required)}.items():
        if not gates or not set(gates) <= identifiers:
            raise RuntimeError(f"missing production acceptance tests: {boundary}")


def main() -> int:
    if not Path("/.dockerenv").is_file():
        print("Run this verifier in Docker; see README.md", file=sys.stderr)
        return 1
    for directory in ("scripts", "tests", "hermes_outcome_loop"):
        for path in (ROOT / directory).rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    require_production_gates(test_ids(suite))
    print(f"Repository verification: {suite.countTestCases()} discovered tests", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
