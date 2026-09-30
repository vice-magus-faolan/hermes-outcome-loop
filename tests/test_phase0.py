# SPDX-License-Identifier: GPL-3.0-or-later
"""Harness regressions plus a mandatory, deliberately red feasibility gate.

No fake dispatch adapter is used as integration evidence. Unit tests below
exercise only harness safety and missing-prerequisite behavior.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Phase-0 harness script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_script("phase0_probe")
runtime = load_script("phase0_runtime")


class HarnessSafetyTests(unittest.TestCase):
    """No dependency provisioning, live paths or inherited worker identity."""

    def test_missing_runtime_prerequisite_fails(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "HERMES_PHASE0_SOURCE"):
                probe.prerequisites()

    def test_child_drops_live_board_identity_and_credentials(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp).resolve()
            poison = {"HERMES_KANBAN_DB": "/not-a-probe/kanban.db",
                      "HERMES_KANBAN_TASK": "not-a-probe",
                      "HERMES_KANBAN_RUN_ID": "999", "OPENAI_API_KEY": "synthetic"}
            with patch.dict(os.environ, poison):
                env = probe.child_environment(base)
            self.assertFalse(set(poison) & set(env))
            for key in ("HOME", "HERMES_HOME", "HERMES_KANBAN_HOME", "TMPDIR"):
                self.assertTrue(Path(env[key]).resolve().is_relative_to(base))

    def test_inner_refuses_inherited_board_override_before_import(self):
        with tempfile.TemporaryDirectory(prefix="outcome-phase0-", dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp).resolve()
            env = probe.child_environment(base)
            env["HERMES_KANBAN_DB"] = "/not-a-probe/kanban.db"
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(RuntimeError, "inherited runtime/worker override"):
                    runtime.validate_isolation(base)

    def test_inner_refuses_symlink_escape_before_import(self):
        with tempfile.TemporaryDirectory(prefix="outcome-phase0-", dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp).resolve()
            env = probe.child_environment(base)
            board_root = Path(env["HERMES_KANBAN_HOME"])
            board_root.rmdir()
            board_root.symlink_to(base.parent, target_is_directory=True)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(RuntimeError, "unsafe isolation path"):
                    runtime.validate_isolation(base)

    def test_interpreter_symlink_keeps_venv_launch_contract(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp)
            source = base / "source"
            (source / "hermes_cli").mkdir(parents=True)
            (source / "hermes_cli/plugins.py").touch()
            interpreter = base / "venv/bin/python"
            interpreter.parent.mkdir(parents=True)
            interpreter.symlink_to(sys.executable)
            with patch.dict(os.environ, {"HERMES_PHASE0_SOURCE": str(source),
                                         "HERMES_PHASE0_PYTHON": str(interpreter)}, clear=True):
                self.assertEqual(probe.prerequisites()[1], interpreter)

    def test_timeout_reaps_disposable_process(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp)
            script = base / "slow.py"
            script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            with self.assertRaises(subprocess.TimeoutExpired):
                probe.run_child([sys.executable, str(script)], base, {}, timeout=0.1)

    def test_json_record_is_deterministic_and_unicode_safe(self):
        import json
        body = runtime.record(1, "caf\u00e9\nquoted \"evidence\"")
        self.assertEqual(body, runtime.record(1, "caf\u00e9\nquoted \"evidence\""))
        self.assertEqual(json.loads(body.removeprefix(runtime.MARKER))["record_id"], "probe_1")


class NativeProbeTests(unittest.TestCase):
    """Real disposable-board results, no skip when Hermes is unavailable."""

    @classmethod
    def setUpClass(cls):
        cls.report = probe.collect()

    def test_exercised_native_boundaries(self):
        report = self.report
        self.assertTrue(report["headless_registered_plugin_dispatch"])
        self.assertTrue(report["isolation"])
        self.assertTrue(report["explicit_headless_board_routing"])
        for key in ("post_done_append_and_readback", "native_author_and_time",
                    "delivery_task_runs_and_existing_events_preserved",
                    "only_new_commented_events", "append_returns_distinct_monotonic_ids"):
            self.assertTrue(report["history"][key], key)
        self.assertTrue(report["redaction"]["json_remains_parseable"])
        self.assertTrue(report["sizes"]["exact_readback"])
        self.assertEqual(report["observer"][0]["profile"], "phase0-a")

    def test_required_phase0_feasibility(self):
        report = self.report
        self.assertTrue(report["history"]["read_has_native_ids"],
                        "NO-GO: public kanban_show omits required native comment IDs; "
                        "operator must approve revised ordering or a supported API")
        self.assertEqual(report["not_exercised"], [],
                         "NO-GO: required feasibility probes remain unexercised")
        self.assertTrue(report["feasible"])
