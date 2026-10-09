#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run repository checks; fail if discovery yields no tests or Phase 0 is no-go.

The host entry point requires an already-local HERMES_OUTCOME_IMAGE content ID.
All required native tests run inside the restricted Docker acceptance runner.
Missing images/dependencies and unsupported required interfaces fail, never skip.
"""
from __future__ import annotations

import ast
import argparse
import json
import os
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside-docker", action="store_true")
    args = parser.parse_args()
    if not args.inside_docker:
        from docker_acceptance import run
        image = os.environ.get("HERMES_OUTCOME_IMAGE")
        if not image:
            print("ERROR: required pre-provisioned Docker image: HERMES_OUTCOME_IMAGE", file=sys.stderr)
            return 1
        return run(image)
    from container_policy import require_container
    require_container()
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
    required_native = {
        "test_native.ProductionNativeTests.test_results_retry_unfinished_and_full_native_history",
        "test_native.ProductionNativeTests.test_restart_profiles_and_actual_parallel_races",
        "test_native.ProductionNativeTests.test_fail_observationally_and_admission_readback",
        "test_packaging.PackagingNativeTests.test_supported_install_scan_admission_registration_and_uninstall",
        "test_packaging.DistributionTests.test_directory_plugin_has_closed_reproducible_distribution",
        "test_packaging.DistributionTests.test_incomplete_symlink_and_existing_output_fail_closed",
        "test_packaging_regressions.PackagingRegressionTests.test_index_cache_removal_keeps_distribution_bytes",
        "test_packaging_regressions.PackagingRegressionTests.test_index_cache_removal_refuses_symlink_escape",
        "test_packaging_regressions.ProfileBarrierRegressionTests.test_child_failure_is_not_reported_as_barrier_timeout",
        "test_packaging_regressions.ProfileBarrierRegressionTests.test_late_startup_uses_shared_deadline",
        "test_packaging_regressions.ProfileBarrierRegressionTests.test_race_child_receives_same_deadline_and_finite_timeout",
        "test_packaging_regressions.ProfileBarrierRegressionTests.test_shared_deadline_still_bounds_barrier",
        "test_phase0.NativeProbeTests.test_causal_worker_failure_and_storage_details",
        "test_phase0.NativeProbeTests.test_exercised_native_boundaries",
        "test_phase0.NativeProbeTests.test_required_phase0_feasibility",
    }
    if not required_native <= test_ids(suite):
        raise RuntimeError("mandatory production-native integration discovery missing")
    count = suite.countTestCases()
    if count == 0:
        print("ERROR: no tests discovered", file=sys.stderr)
        return 1
    print(f"Repository verification: {count} discovered tests", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
