# SPDX-License-Identifier: GPL-3.0-or-later
"""Mandatory real-Hermes integration plus harness path fences. No silent skips."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from native_probe import collect, install_fixture, validate_paths


class NativeSafetyTests(unittest.TestCase):
    def test_fixture_environment_discards_live_worker_credentials(self):
        with tempfile.TemporaryDirectory(prefix="outcome-phase0-native-", dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp).resolve()
            with patch.dict(os.environ, {"HERMES_KANBAN_DB": "/outside/board.db",
                                         "HERMES_KANBAN_TASK": "outside", "OPENAI_API_KEY": "synthetic"}):
                env = install_fixture(base, "phase0-a")
                self.assertFalse({"HERMES_KANBAN_DB", "HERMES_KANBAN_TASK", "OPENAI_API_KEY"} & env.keys())
                with patch.dict(os.environ, env, clear=True):
                    validate_paths(base)
                    for key in ("HOME", "HERMES_HOME", "HERMES_KANBAN_HOME", "TMPDIR"):
                        poisoned = dict(env, **{key: str(base.parent)})
                        with patch.dict(os.environ, poisoned, clear=True):
                            with self.assertRaises(RuntimeError):
                                validate_paths(base)


class ProductionNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = collect(debug=True)

    def test_results_retry_unfinished_and_full_native_history(self):
        for name in ("define_view_results_regression", "unfinished_rejected",
                     "native_review_completion_preserved", "stable_retry_no_write"):
            self.assertTrue(self.report[name], name)

    def test_restart_profiles_and_actual_parallel_races(self):
        for name in ("restart_profiles_identical", "parallel_same_id_retries_conflicts_forks"):
            self.assertTrue(self.report[name], name)

    def test_fail_observationally_and_admission_readback(self):
        for name in ("disabled_malformed_raised_isolation", "read_write_readback_failures",
                     "sensitive_size_stored_readback", "no_completion_hook_dependency"):
            self.assertTrue(self.report[name], name)
