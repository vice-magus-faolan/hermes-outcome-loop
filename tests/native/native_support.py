# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable native-plugin test setup; no host installation or model provider."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERMES_SHA = "f42f579cf8bac4918ac9599bece71618afadd846"


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def install_fixture(base: Path, profile: str, enabled: bool = True, reuse_profile: bool = False) -> dict[str, str]:
    """Install a test loader in a new isolated profile; discard ambient credentials."""
    home = base / "host-home/.hermes/profiles" / profile
    for path in (home, base / "board-root", base / "tmp"):
        path.mkdir(parents=True, exist_ok=True)
    if enabled and not reuse_profile:
        target = home / "plugins/outcome-native-test"
        shutil.copytree(ROOT / "tests/fixtures/native_plugin", target, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "hermes_outcome_loop", target / "hermes_outcome_loop",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "schemas", target / "schemas")
        shutil.copyfile(ROOT / "__init__.py", target / "_production_entry.py")
    (home / "config.yaml").write_text(
        "toolsets: [kanban, outcome, native_test]\nplugins:\n  enabled: " +
        ("[outcome-native-test]" if enabled else "[]") + "\n", encoding="utf-8")
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
    env.update(HOME=str(base / "host-home"), HERMES_HOME=str(home), HERMES_PROFILE=profile,
               HERMES_KANBAN_HOME=str(base / "board-root"), HERMES_KANBAN_BOARD="outcome-test",
               TMPDIR=str(base / "tmp"), HERMES_ENABLE_PROJECT_PLUGINS="false",
               HERMES_DISABLE_LAZY_INSTALLS="true", PYTHONDONTWRITEBYTECODE="1")
    return env


def validate_paths(base: Path) -> None:
    """Refuse live or escaped home/board paths before importing native Hermes."""
    require(base.name.startswith("outcome-native-"), "native integration root is not disposable")
    for key in ("HOME", "HERMES_HOME", "HERMES_KANBAN_HOME", "TMPDIR"):
        path = Path(os.environ[key])
        require(path.resolve(strict=True) == path and path.is_relative_to(base),
                "native integration path escaped disposable root")
    require(not {"HERMES_KANBAN_TASK", "HERMES_KANBAN_DB", "HERMES_KANBAN_RUN_ID"}.intersection(os.environ),
            "native integration inherited worker identity")
    require(Path(os.environ["HERMES_KANBAN_HOME"]) == base / "board-root", "native board root mismatch")


def collect(debug: bool = False) -> dict:
    """Run the real registered-plugin cases with finite process/container bounds."""
    require(Path("/.dockerenv").is_file(), "native integration must run in Docker")
    source = Path(os.environ["HERMES_TEST_SOURCE"]).resolve(strict=True)
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    require(sha == HERMES_SHA, "native integration requires the pinned Hermes revision")
    with tempfile.TemporaryDirectory(prefix="outcome-native-", dir=os.environ["TMPDIR"]) as tmp:
        base = Path(tmp).resolve(strict=True)
        env = install_fixture(base, "outcome-test-a")
        args = [sys.executable, "-B", str(ROOT / "tests/native/native_runtime.py"), str(source), str(base)]
        process = subprocess.Popen(args, cwd=base, env=env, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            output, errors = process.communicate(timeout=180)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        if process.returncode:
            if debug:
                print(errors[-4096:].replace(str(base), "<disposable-root>")
                      .replace(str(source), "<hermes-source>"), file=sys.stderr)
            raise RuntimeError("production-native integration failed")
        report = json.loads(output)
        require(report["hermes_sha"] == HERMES_SHA, "native integration pin mismatch")
        return report
