#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run a registered-plugin probe in a fresh, credential-free Hermes home.

Requires HERMES_PHASE0_SOURCE (read-only installed source checkout) and
HERMES_PHASE0_PYTHON (its already provisioned interpreter). No install/update,
external LLM, gateway or private Kanban API occurs. A scripted loopback provider
drives a real dispatcher worker; data writes still use native tools, not CLI.
Evidence collection can succeed with feasibility=false; --require-feasible is
an explicit failing acceptance gate, also exercised by scripts/verify.py.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def prerequisites() -> tuple[Path, Path]:
    """Fail loudly rather than silently skipping required runtime evidence."""
    paths = []
    for key in ("HERMES_PHASE0_SOURCE", "HERMES_PHASE0_PYTHON"):
        value = os.environ.get(key)
        if not value:
            raise RuntimeError(f"required runtime prerequisite: {key}")
        path = Path(value).expanduser().absolute()
        if not path.exists():
            raise RuntimeError(f"required runtime prerequisite does not exist: {key}")
        # Preserve a venv's bin/python symlink: resolving it loses sys.prefix.
        paths.append(path)
    source, interpreter = paths
    if not (source / "hermes_cli/plugins.py").is_file():
        raise RuntimeError("HERMES_PHASE0_SOURCE is not a Hermes source checkout")
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise RuntimeError("HERMES_PHASE0_PYTHON is not executable")
    if sys.platform != "linux" or not Path("/proc/self/stat").is_file():
        raise RuntimeError("Phase-0 worker cleanup currently requires Linux /proc")
    scratch = os.environ.get("TMPDIR")
    if not scratch or not Path(scratch).is_dir():
        raise RuntimeError("required runtime prerequisite: existing writable TMPDIR")
    return source, interpreter


def child_environment(base: Path) -> dict[str, str]:
    """Allowlist ambient variables; replace ALL identity/board/home paths."""
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL")
           if key in os.environ}
    home = base / "host-home"
    profile = home / ".hermes/profiles/phase0-a"
    boards = base / "board-root"
    for path in (home, profile, boards, base / "tmp"):
        path.mkdir(parents=True)
    env.update({
        "HOME": str(home), "HERMES_HOME": str(profile),
        "HERMES_PROFILE": "phase0-a", "HERMES_KANBAN_HOME": str(boards),
        "HERMES_KANBAN_BOARD": "phase0", "TMPDIR": str(base / "tmp"),
        "HERMES_ENABLE_PROJECT_PLUGINS": "false",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
    })
    return env


def run_child(command: list[str], base: Path, env: dict[str, str], timeout: float = 120) -> tuple[int, str, str]:
    """Bound the whole disposable process group, not only the direct child.

    POSIX is an explicit Phase-0 harness prerequisite. Descendant cleanup is
    unrelated to in-process plugin failure isolation.
    """
    if os.name != "posix":
        raise RuntimeError("Phase-0 harness currently requires POSIX process groups")
    process = subprocess.Popen(command, cwd=base, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def cleanup_workers(base: Path) -> None:
    """Reap detached fixture workers using public spawn-hook cleanup receipts."""
    receipt = base / "worker-pids.jsonl"
    if not receipt.exists():
        return
    for row in receipt.read_text(encoding="utf-8").splitlines():
        pid = json.loads(row)["pid"]
        try:
            environment = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            expected = f"HOME={base / 'host-home'}".encode()
            if expected not in environment or os.getpgid(pid) != pid:
                continue  # never signal a recycled or non-fixture process
            os.killpg(pid, signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass


def collect(debug: bool = False) -> dict:
    """Collect sanitized facts only; destroy every disposable native record."""
    source, interpreter = prerequisites()
    with tempfile.TemporaryDirectory(prefix="outcome-phase0-", dir=os.environ.get("TMPDIR")) as tmp:
        base = Path(tmp).resolve(strict=True)
        env = child_environment(base)
        profile = Path(env["HERMES_HOME"])
        shutil.copytree(ROOT / "tests/fixtures/phase0_plugin", profile / "plugins/phase0-probe")
        # This is a newly authored disposable fixture, not an operator config.
        (profile / "config.yaml").write_text(
            "toolsets: [kanban]\nplugins:\n  enabled: [phase0-probe]\n",
            encoding="utf-8")
        try:
            returncode, stdout, stderr = run_child(
                [str(interpreter), "-B", str(ROOT / "scripts/phase0_runtime.py"), str(source), str(base)],
                base, env, timeout=240)
        finally:
            cleanup_workers(base)
        if returncode:
            # Do not propagate board snapshots or runtime paths into public output.
            if debug:
                print(stderr.replace(str(base), "<disposable-root>")
                      .replace(str(source), "<hermes-source>"), file=sys.stderr)
            raise RuntimeError("native probe execution failed; inspect locally with --debug-runtime")
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("native probe returned non-JSON output") from error


def main() -> int:
    """Print portable evidence and optionally enforce approved feasibility."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-feasible", action="store_true")
    parser.add_argument("--debug-runtime", action="store_true",
                        help="show runtime failure diagnostics with runtime paths removed")
    args = parser.parse_args()
    report = collect(debug=args.debug_runtime)
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(args.require_feasible and not report["feasible"])


if __name__ == "__main__":
    raise SystemExit(main())
