# SPDX-License-Identifier: GPL-3.0-or-later
"""Narrow regressions for offline backend resolution and real-profile barriers."""
from concurrent.futures import Future
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class PackagingRegressionTests(unittest.TestCase):
    def test_index_cache_removal_keeps_distribution_bytes(self):
        from packaging_runtime import clear_index_metadata
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp)
            cache = base / "host-home/.hermes/cache/uv"
            for name in ("simple-v18", "flat-index-v2", "archive-v0", "wheels-v5"):
                (cache / name).mkdir(parents=True)
                (cache / name / "retained").write_bytes(b"fixture")
            self.assertEqual(clear_index_metadata(base), 2)
            self.assertFalse((cache / "simple-v18").exists())
            self.assertFalse((cache / "flat-index-v2").exists())
            self.assertEqual((cache / "archive-v0/retained").read_bytes(), b"fixture")
            self.assertEqual((cache / "wheels-v5/retained").read_bytes(), b"fixture")

    def test_index_cache_removal_refuses_symlink_escape(self):
        from packaging_runtime import clear_index_metadata
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp) / "base"
            cache = base / "host-home/.hermes/cache/uv"
            cache.mkdir(parents=True)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "retained").touch()
            (cache / "simple-v18").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "cache metadata escaped"):
                clear_index_metadata(base)
            self.assertTrue((outside / "retained").exists())


class ProfileBarrierRegressionTests(unittest.TestCase):
    def test_late_startup_uses_shared_deadline(self):
        from phase0_extended import wait_race_readers
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp)
            futures = [Future(), Future()]
            def ready(_):
                for profile in ("phase0-a", "phase0-b"):
                    (base / ("race-ready-" + profile)).touch()
            with patch("phase0_extended.time.monotonic", return_value=11), \
                    patch("phase0_extended.time.sleep", side_effect=ready):
                wait_race_readers(base, futures, deadline=45)

    def test_child_failure_is_not_reported_as_barrier_timeout(self):
        from phase0_extended import wait_race_readers
        failure = Future()
        failure.set_exception(RuntimeError("native child import failed"))
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            with self.assertRaisesRegex(RuntimeError, "native child import failed"):
                wait_race_readers(Path(tmp), [failure, Future()], deadline=0)

    def test_shared_deadline_still_bounds_barrier(self):
        from phase0_extended import wait_race_readers
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            with patch("phase0_extended.time.monotonic", return_value=46):
                with self.assertRaisesRegex(RuntimeError, "read barrier.*phase0-a.*phase0-b"):
                    wait_race_readers(Path(tmp), [Future(), Future()], deadline=45)

    def test_race_child_receives_same_deadline_and_finite_timeout(self):
        import phase0_extended
        result = type("Result", (), {"returncode": 0, "stderr": "", "stdout": json.dumps({"ok": True})})()
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            with patch.object(phase0_extended.subprocess, "run", return_value=result) as run:
                phase0_extended.reopen(ROOT, Path(tmp), "synthetic", "race", race_deadline=45)
            self.assertEqual(run.call_args.kwargs["env"]["OUTCOME_PHASE0_RACE_DEADLINE"], "45")
            self.assertEqual(run.call_args.kwargs["timeout"], 60)
