# SPDX-License-Identifier: GPL-3.0-or-later
"""Runner policy tests, not real-Hermes acceptance evidence."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("docker_acceptance", ROOT / "scripts/docker_acceptance.py")
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load Docker runner")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
import docker_build_preflight as preflight


class DockerHarnessTests(unittest.TestCase):
    def test_acceptance_limits_and_no_ambient_mounts(self):
        args = runner.create_command("owned-name", "sha256:" + "1" * 64, Path("/staged/source"))
        for item in ("--read-only", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                     "--cpus=2", "--memory=2g", "--memory-swap=2g", "--pids-limit=256", "--pull=never",
                     "--user=65532:65532", "--log-driver=local", "--log-opt=max-size=1m", "--log-opt=max-file=1"):
            self.assertIn(item, args)
        self.assertIn("/scratch:rw,nosuid,nodev,size=536870912,mode=1777", args)
        self.assertEqual([x for x in args if x.startswith("type=bind")],
                         ["type=bind,src=/staged/source,dst=/source,readonly"])
        self.assertNotIn("--privileged", args)

    def test_image_must_be_literal_local_content_identity(self):
        runner.validate_image("sha256:" + "a" * 64)
        for value in ("latest", "python:3.14", "sha256:ABC", "sha256:" + "a" * 63):
            with self.assertRaises(ValueError):
                runner.validate_image(value)

    def test_staging_refuses_runtime_secrets_symlinks_and_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source, target = base / "repo", base / "stage"
            source.mkdir()
            (source / "safe.py").write_text("print('safe')")
            runner.stage_files(source, target, ["safe.py"])
            self.assertEqual((target / "safe.py").read_text(), "print('safe')")
            for name in (".integration/hermes/a.py", ".env", ".venv/bin/python", "../escape", "/absolute"):
                with self.assertRaises(ValueError):
                    runner.stage_files(source, base / "other", [name])
            (source / "link.py").symlink_to(source / "safe.py")
            with self.assertRaises(ValueError):
                runner.stage_files(source, base / "other", ["link.py"])
            with self.assertRaises(ValueError):
                runner.stage_files(source, base / "overflow", ["safe.py"], limit=1)

    def test_unknown_build_budget_is_not_a_capacity_pass(self):
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            runner.require_budget(10 * 1024**3, None)
        with self.assertRaisesRegex(RuntimeError, "reserve"):
            runner.require_budget(3 * 1024**3, 2 * 1024**3)
        runner.require_budget(5 * 1024**3, 2 * 1024**3)

    def test_teardown_failure_keeps_primary_exit(self):
        self.assertEqual(runner.final_status(7, ["cleanup failed"]), 7)
        self.assertNotEqual(runner.final_status(0, ["cleanup failed"]), 0)
        item = {"Id": "a" * 64, "Config": {"Labels": {runner.OWNER_KEY: runner.OWNER_VALUE}}}
        with patch.object(runner, "inspect_container", return_value=item) as inspect, patch.object(runner, "cleanup") as cleanup:
            runner.cleanup_attempt(None, "exact-owned-name")
            inspect.assert_called_once_with("exact-owned-name")
            cleanup.assert_called_once_with("a" * 64)

    def test_container_identity_requires_owned_label(self):
        item = {"Id": "a" * 64, "Config": {"Labels": {runner.OWNER_KEY: runner.OWNER_VALUE}}}
        self.assertEqual(runner.owned_identity(item), "a" * 64)
        item["Config"]["Labels"] = {}
        with self.assertRaises(RuntimeError):
            runner.owned_identity(item)

    def test_construction_stores_share_one_filesystem_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch.object(preflight.shutil, "disk_usage") as usage:
                usage.return_value.free = 5 * 1024**3
                with self.assertRaisesRegex(RuntimeError, "reserve"):
                    preflight.aggregate_stores({"docker": base, "containerd": base},
                                               {"docker": 2 * 1024**3, "containerd": 2 * 1024**3})
                with self.assertRaisesRegex(RuntimeError, "unknown"):
                    preflight.aggregate_stores({"docker": base}, {"docker": None})

    def test_host_cannot_opt_into_native_with_a_flag(self):
        import container_policy
        with patch.object(container_policy.os, "getuid", return_value=1000):
            with self.assertRaisesRegex(RuntimeError, "non-root Docker runner"):
                container_policy.require_container()
