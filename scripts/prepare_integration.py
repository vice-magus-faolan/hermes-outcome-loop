#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit repo-local CI runtime preparation, never a live Hermes installation.

Uses Hermes's supported PM fresh-environment APIs and frozen core export. Does
not mutate a selected runtime, source lock, profile, board or shared dependency.
Network acquisition is explicit here; verification itself never installs anything.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HERMES_SHA = "f42f579cf8bac4918ac9599bece71618afadd846"
HERMES_URL = "https://github.com/vice-magus-faolan/hermes-agent.git"


def run(command, env, cwd):
    subprocess.run(command, env=env, cwd=cwd, check=True, timeout=1200)


def prepare(source=None):
    """Refuse reused/symlinked build outputs; return explicit verifier prerequisites."""
    base = ROOT / ".integration"
    base.mkdir(exist_ok=False)
    if base.resolve() != base:
        raise RuntimeError("integration build path is not literal")
    home = base / "home"
    home.mkdir()
    scratch = base / "tmp"
    scratch.mkdir()
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
    env.update(HOME=str(home), HERMES_HOME=str(home / ".hermes"), TMPDIR=str(scratch),
               PYTHONDONTWRITEBYTECODE="1", HERMES_DISABLE_LAZY_INSTALLS="true")
    if source is None:
        source = base / "hermes"
        run(["git", "init", str(source)], env, base)
        run(["git", "-C", str(source), "fetch", "--depth", "1", HERMES_URL, HERMES_SHA], env, base)
        run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], env, base)
    source = Path(source).resolve(strict=True)
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if sha != HERMES_SHA:
        raise RuntimeError("untested Hermes source version")
    env["PYTHONPATH"] = str(source)
    exported = base / "core-requirements.txt"
    common = [sys.executable, "-B", "-m", "pm.build_env"]
    run(common + ["--source", str(source), "--export-requirements", str(exported),
                  "--cache", str(base / "cache")], env, base)
    requirements = exported.read_text() + "\n" + (ROOT / "requirements.txt").read_text()
    combined = base / "runtime-requirements.txt"
    combined.write_text(requirements, encoding="utf-8")
    run(common + ["--requirements", str(combined), "--out", str(base / "runtime"),
                  "--cache", str(base / "cache")], env, base)
    result = {"HERMES_PHASE0_SOURCE": str(source),
              "HERMES_PHASE0_PYTHON": str(base / "runtime/bin/python"), "TMPDIR": str(scratch)}
    (base / "prerequisites.json").write_text(json.dumps(result), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="optional read-only checkout at the exact tested SHA")
    args = parser.parse_args()
    print(json.dumps(prepare(args.source), indent=2))


if __name__ == "__main__":
    main()
