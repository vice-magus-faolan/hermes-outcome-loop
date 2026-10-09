# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable distribution layout, reproducibility and rejected unsafe inputs."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DistributionTests(unittest.TestCase):
    def test_incomplete_symlink_and_existing_output_fail_closed(self):
        from package_plugin import build, FILES
        import shutil
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            base = Path(tmp)
            source = base / "source"
            for name in FILES:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            schema = source / "schemas/common.schema.json"
            schema.unlink()
            with self.assertRaises(FileNotFoundError):
                build(source, base / "missing")
            self.assertFalse((base / "missing").exists())
            schema.symlink_to(ROOT / "schemas/common.schema.json")
            with self.assertRaises(ValueError):
                build(source, base / "symlink")
            self.assertFalse((base / "symlink").exists())
            schema.unlink()
            shutil.copyfile(ROOT / "schemas/common.schema.json", schema)
            existing = base / "existing"
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                build(source, existing)
            self.assertEqual(list(existing.iterdir()), [])

    def test_directory_plugin_has_closed_reproducible_distribution(self):
        from package_plugin import build
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            first = build(ROOT, Path(tmp) / "first")
            second = build(ROOT, Path(tmp) / "second")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            import tarfile
            with tarfile.open(first) as archive:
                names = set(archive.getnames())
                for name in ("plugin.yaml", "__init__.py", "LICENSE", "CONTRIBUTORS.md",
                             "hermes_outcome_loop/records.py", "schemas/common.schema.json"):
                    self.assertIn("hermes-outcome-loop/" + name, names)
                self.assertFalse(any("tests/" in name or ".git" in name for name in names))
