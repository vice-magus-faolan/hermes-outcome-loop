#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small fail-closed Docker runner. Never pulls, builds or mounts a live runtime.

Construction is a separate public-only phase. Smoke exercises runner mechanics,
not Hermes acceptance; a missing candidate image is a failure, never a skip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
HERMES_SHA = "f42f579cf8bac4918ac9599bece71618afadd846"
OWNER_KEY = "org.hermes-outcome-loop.test"
OWNER_VALUE = "disposable-acceptance-v1"
RESERVE = 2 * 1024**3
SOURCE_LIMIT = 16 * 1024**2
IMAGE_PATTERN = r"sha256:[a-f0-9]{64}"
FORBIDDEN = {".git", ".integration", ".venv", "__pycache__", ".env", "auth.json", "credentials.json"}


def validate_image(image: str) -> None:
    """Only exact already-local content IDs; never tags or implicit pulls."""
    if not re.fullmatch(IMAGE_PATTERN, image):
        raise ValueError("candidate must be a literal local sha256 image ID")


def require_budget(available: int, peak: int | None) -> None:
    """A measured peak or enforceable upper bound is required before construction."""
    if peak is None or type(peak) is not int or peak <= 0:
        raise RuntimeError("construction peak unknown; choose a budgeted runner/storage")
    if available - peak < RESERVE:
        raise RuntimeError("construction would violate the 2 GiB reserve")


def stage_files(source: Path, target: Path, names: list[str], limit: int = SOURCE_LIMIT) -> None:
    """Copy only bounded literal regular source files, excluding runtime state."""
    total = 0
    source = source.resolve(strict=True)
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or FORBIDDEN.intersection(relative.parts):
            raise ValueError("unsafe source input")
        path = source / relative
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError("source must be a literal regular file")
        total += path.stat().st_size
        if total > limit:
            raise ValueError("source input exceeds bounded handoff")
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)


def create_command(name: str, image: str, source: Path, smoke: bool = False) -> list[str]:
    """Network denied also denies external providers; loopback fixture remains local."""
    program = (["python3", "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_docker_harness.py", "-v"]
               if smoke else ["/opt/runtime/bin/python", "-B", "scripts/verify.py", "--inside-docker"])
    return ["docker", "create", "--name", name, "--label", f"{OWNER_KEY}={OWNER_VALUE}",
            "--pull=never", "--read-only", "--network=none", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--user=65532:65532", "--cpus=2",
            "--memory=2g", "--memory-swap=2g", "--pids-limit=256",
            "--log-driver=local", "--log-opt=max-size=1m", "--log-opt=max-file=1",
            "--log-opt=compress=false",
            "--tmpfs", "/scratch:rw,nosuid,nodev,size=536870912,mode=1777",
            "--mount", f"type=bind,src={source},dst=/source,readonly", "--workdir=/source",
            "--env=HOME=/scratch/home", "--env=TMPDIR=/scratch",
            "--env=PYTHONDONTWRITEBYTECODE=1", "--env=HERMES_DISABLE_LAZY_INSTALLS=true",
            "--env=HERMES_PHASE0_SOURCE=/opt/hermes", "--env=HERMES_PHASE0_PYTHON=/opt/runtime/bin/python",
            "--entrypoint", program[0], image, *program[1:]]


def command(args: list[str], timeout: int = 30, merge_stderr: bool = False) -> str:
    """No inherited credentials or worker pins are passed to Docker commands."""
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
    result = subprocess.run(args, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
                            text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command failed: {args[:2]} (exit {result.returncode}): {(result.stderr or '')[:2048]}")
    if len(result.stdout.encode()) > 2 * 1024**2:
        raise RuntimeError("bounded evidence export exceeded")
    return result.stdout.strip()


def inspect_container(identity: str) -> dict:
    return json.loads(command(["docker", "container", "inspect", identity]))[0]


def owned_identity(item: dict) -> str:
    if item["Config"].get("Labels", {}).get(OWNER_KEY) != OWNER_VALUE:
        raise RuntimeError("refusing cleanup of unowned container")
    identity = item["Id"]
    if not re.fullmatch(r"[a-f0-9]{64}", identity):
        raise RuntimeError("invalid container identity")
    return identity


def verify_limits(item: dict, source: Path) -> None:
    """Read back engine configuration before starting any candidate code."""
    host = item["HostConfig"]
    expected = {"ReadonlyRootfs": True, "NetworkMode": "none", "Memory": 2 * 1024**3,
                "MemorySwap": 2 * 1024**3, "NanoCpus": 2 * 10**9, "PidsLimit": 256}
    if any(host.get(key) != value for key, value in expected.items()):
        raise RuntimeError("engine acceptance limits mismatch")
    if item["Config"]["User"] != "65532:65532" or host.get("CapDrop") != ["ALL"]:
        raise RuntimeError("engine non-root/capability mismatch")
    if "no-new-privileges" not in host.get("SecurityOpt", []):
        raise RuntimeError("engine privilege restriction missing")
    mounts = item["Mounts"]
    if len(mounts) != 1 or mounts[0]["Source"] != str(source) or mounts[0]["Destination"] != "/source" or mounts[0]["RW"]:
        raise RuntimeError("engine source mount mismatch")
    if host.get("Tmpfs") != {"/scratch": "rw,nosuid,nodev,size=536870912,mode=1777"}:
        raise RuntimeError("engine scratch budget mismatch")


def source_digest(stage: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(stage)).encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def cleanup(identity: str) -> None:
    """Exact label + ID match before removal, global list readback afterward."""
    if owned_identity(inspect_container(identity)) != identity:
        raise RuntimeError("container identity changed")
    command(["docker", "container", "rm", "--force", identity])
    remaining = command(["docker", "container", "ls", "--all", "--no-trunc", "--format", "{{.ID}}"])
    if identity in remaining.splitlines():
        raise RuntimeError("owned container removal not verified")


def cleanup_attempt(identity: str | None, name: str) -> None:
    """A failed create response may still have persisted the exact named resource."""
    if identity is None:
        identity = owned_identity(inspect_container(name))
    cleanup(identity)


def final_status(primary: int, cleanup_errors: list[str]) -> int:
    return primary if primary else int(bool(cleanup_errors))


def check_candidate(image: str, smoke: bool) -> None:
    validate_image(image)
    item = json.loads(command(["docker", "image", "inspect", image]))[0]
    if item["Id"] != image:
        raise RuntimeError("candidate identity mismatch")
    if not smoke and item["Config"].get("Labels", {}).get("org.hermes-outcome-loop.hermes-sha") != HERMES_SHA:
        raise RuntimeError("candidate lacks required Hermes pin; provision separately")


def run(image: str, smoke: bool = False) -> int:
    """Keep primary failure even on teardown failure; never delete images or volumes."""
    check_candidate(image, smoke)
    require_budget(shutil.disk_usage(os.environ["TMPDIR"]).free, SOURCE_LIMIT + 2 * 1024**2)
    names = command(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]).split("\0")
    identity = None
    primary = 1
    errors = []
    report = {"mode": "smoke-not-native" if smoke else "native-acceptance", "image_id": image,
              "hermes_sha": HERMES_SHA, "cleanup_verified": False}
    with tempfile.TemporaryDirectory(prefix="outcome-docker-", dir=os.environ["TMPDIR"]) as tmp:
        stage = Path(tmp) / "source"
        # Parent must be traversable by the non-root container UID.
        Path(tmp).chmod(0o755)
        stage_files(ROOT, stage, [name for name in names if name])
        report["source_sha256"] = source_digest(stage)
        report["source_commit"] = command(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
        name = "outcome-test-" + uuid.uuid4().hex
        report["container_name"] = name
        try:
            identity = command(create_command(name, image, stage, smoke))
            report["container_id"] = identity
            owned_identity(inspect_container(identity))
            verify_limits(inspect_container(identity), stage)
            report["limits_verified"] = True
            command(["docker", "start", identity])
            primary = int(command(["docker", "wait", identity], timeout=1200))
            print(command(["docker", "logs", identity], merge_stderr=True))
            report["container_exit"] = primary
        except (RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
            primary = primary or 1
            report["primary_failure"] = str(error)
        finally:
            try:
                cleanup_attempt(identity, name)
                report["cleanup_verified"] = True
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                errors.append(type(error).__name__)
    report["cleanup_errors"] = errors
    report["exit_code"] = final_status(primary, errors)
    print(json.dumps(report, sort_keys=True))
    return report["exit_code"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--smoke", action="store_true", help="runner-only tests; NEVER acceptance")
    args = parser.parse_args()
    return run(args.image, args.smoke)


if __name__ == "__main__":
    raise SystemExit(main())
