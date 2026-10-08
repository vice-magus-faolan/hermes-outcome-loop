#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Production-native integration launcher; no dependency preparation or live paths."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from phase0_probe import child_environment, prerequisites, run_child
from docker_acceptance import HERMES_SHA

ROOT = Path(__file__).resolve().parents[1]


def install_fixture(base: Path, profile: str, enabled: bool = True, reuse_profile: bool = False) -> dict[str, str]:
    """Test-only source loader, not distribution install/admission acceptance."""
    env = child_environment(base) if not (base / "host-home").exists() else {
        key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
    home = base / "host-home/.hermes/profiles" / profile
    home.mkdir(parents=True, exist_ok=True)
    if enabled and not reuse_profile:
        target = home / "plugins/outcome-native-test"
        shutil.copytree(ROOT / "tests/fixtures/native_plugin", target, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "hermes_outcome_loop", target / "hermes_outcome_loop",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "schemas", target / "schemas")
    (home / "config.yaml").write_text(
        "toolsets: [kanban, outcome, native_test]\nplugins:\n  enabled: " +
        ("[outcome-native-test]" if enabled else "[]") + "\n", encoding="utf-8")
    env.update(HOME=str(base / "host-home"), HERMES_HOME=str(home), HERMES_PROFILE=profile,
               HERMES_KANBAN_HOME=str(base / "board-root"), HERMES_KANBAN_BOARD="phase0",
               TMPDIR=str(base / "tmp"), HERMES_ENABLE_PROJECT_PLUGINS="false",
               HERMES_DISABLE_LAZY_INSTALLS="true", PYTHONDONTWRITEBYTECODE="1")
    return env


def validate_paths(base: Path) -> None:
    """Must run before importing Hermes or querying native board paths."""
    if not base.name.startswith("outcome-phase0-native-"):
        raise RuntimeError("native integration root is not disposable")
    for key in ("HOME", "HERMES_HOME", "HERMES_KANBAN_HOME", "TMPDIR"):
        path = Path(os.environ[key])
        if path.resolve(strict=True) != path or not path.is_relative_to(base):
            raise RuntimeError("native integration path escaped disposable root")
    for key in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_DB", "HERMES_KANBAN_RUN_ID"):
        if key in os.environ:
            raise RuntimeError("native integration inherited worker identity")
    if Path(os.environ["HERMES_KANBAN_HOME"]) != base / "board-root":
        raise RuntimeError("native integration board root mismatch")


def collect(debug: bool = False) -> dict:
    from container_policy import require_container
    require_container()
    source, interpreter = prerequisites()
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if sha != HERMES_SHA:
        raise RuntimeError("native integration requires the explicit Hermes source pin")
    with tempfile.TemporaryDirectory(prefix="outcome-phase0-native-", dir=os.environ["TMPDIR"]) as tmp:
        base = Path(tmp).resolve(strict=True)
        env = install_fixture(base, "phase0-a")
        code, output, errors = run_child([str(interpreter), "-B", str(ROOT / "scripts/native_runtime.py"),
                                     str(source), str(base)], base, env, timeout=180)
        if code:
            if debug:
                diagnostic = errors[-4096:].replace(str(base), "<disposable-root>").replace(str(source), "<hermes-source>")
                print(re.sub(r"t_[0-9a-f]{8}", "<disposable-task>", diagnostic), file=sys.stderr)
            raise RuntimeError("production-native integration failed; no acceptance receipt")
        report = json.loads(output)
        if report["hermes_sha"] != HERMES_SHA:
            raise RuntimeError("native integration receipt pin mismatch")
        return report


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True))
