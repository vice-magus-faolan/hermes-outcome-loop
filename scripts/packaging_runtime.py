#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Supported native packaging acceptance; never bypass scans or PM publication."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

from native_probe import ROOT, validate_paths
from package_plugin import build, NAME
from phase0_runtime import require
from phase0_snapshot import preserved, snapshot


def command(arguments: list[str], base: Path) -> subprocess.CompletedProcess[str]:
    """Bound native CLI calls and retain their primary failure for redacted diagnostics."""
    result = subprocess.run(arguments, cwd=base, env=os.environ.copy(), capture_output=True,
                            text=True, timeout=240)
    if result.returncode:
        raise RuntimeError("packaging command failed: " + str(arguments[:5]) + "\n" + result.stdout[-4000:] + result.stderr[-4000:])
    return result


class InstalledAPI:
    """Actual distribution loaded by native discovery, without an integration loader fixture."""

    def __init__(self):
        from pm.environments import activate_dependencies
        activate_dependencies(Path(os.environ["HERMES_PHASE0_SOURCE"]))
        from hermes_cli.plugins import get_plugin_manager
        from tools.registry import registry
        import tools.kanban_tools  # noqa: F401
        self.manager = get_plugin_manager()
        self.manager.discover_and_load()
        self.registry = registry

    def call(self, name: str, **arguments) -> dict:
        raw = self.registry.dispatch(name, arguments, scope=self.manager.scope_key)
        if not isinstance(raw, str):
            raise RuntimeError("native dispatch returned non-string result")
        value = json.loads(raw)
        require("error" not in value, "distribution/native operation failed: " + name)
        return value

    def outcome(self, name: str, task: str, payload: dict | None = None) -> dict:
        args: dict = {"board": "phase0", "task_id": task}
        if payload is not None:
            args["contract" if name == "outcome_define" else "observation"] = payload
        reply = self.call(name, **args)
        require(reply["ok"], "distribution outcome acknowledgment failed")
        return reply

    def create(self) -> str:
        return self.call("kanban_create", title="Disposable packaged-plugin acceptance", assignee="phase0-a",
                         board="phase0", completion_contract="local-only")["task_id"]

    def complete(self, task: str) -> None:
        self.call("kanban_request_review", task_id=task, board="phase0", summary="Disposable native review")
        self.call("kanban_complete", task_id=task, board="phase0", summary="Disposable native completion")
        require(self.call("kanban_show", task_id=task, board="phase0")["task"]["status"] == "done",
                "distribution native completion not visible")


def payload(name: str, task: str) -> dict:
    value = copy.deepcopy(json.loads((ROOT / "tests/fixtures/outcome/golden.json").read_text())[name])
    value.pop("payload_sha256")
    value.update(board="phase0", task_id=task)
    if value["type"] == "observation":
        value["observed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value


def workflow(api: InstalledAPI, base: Path) -> tuple[str, dict]:
    task = api.create()
    contract = payload("contract", task)
    require(api.outcome("outcome_define", task, contract)["view"]["state"] == "planned", "definition not planned")
    api.complete(task)
    before = snapshot(base, task)
    require(api.outcome("outcome_check", task)["view"]["state"] == "awaiting_observation", "completion not awaiting")
    confirmed = payload("confirmed", task)
    require(api.outcome("outcome_observe", task, confirmed)["view"]["state"] == "confirmed", "confirmation missing")
    require(api.outcome("outcome_check", task)["view"]["action"] == "NO_ACTION_REQUIRED", "confirmation attention wrong")
    require(api.outcome("outcome_observe", task, confirmed)["acknowledgment"] == "identical_retry", "retry appended")
    regressed = payload("regressed", task)
    reply = api.outcome("outcome_observe", task, regressed)
    require(reply["view"]["state"] == "regressed", "regression missing")
    require(api.outcome("outcome_check", task)["view"]["action"] == "FOLLOWUP_SUGGESTED", "regression attention wrong")
    require(preserved(before, snapshot(base, task), 2), "installed plugin changed delivery history")
    return task, reply["view"]


def git_distribution(directory: Path, base: Path) -> str:
    for args in (["git", "init", str(directory)], ["git", "-C", str(directory), "add", "."],
                 ["git", "-C", str(directory), "-c", "user.name=Disposable acceptance", "-c",
                  "user.email=acceptance@example.invalid", "commit", "-m", "Disposable distribution"]):
        command(args, base)
    return command(["git", "-C", str(directory), "rev-parse", "HEAD"], base).stdout.strip()


def fresh(source: Path, base: Path, action: str, task: str) -> dict:
    result = command([sys.executable, "-B", str(ROOT / "scripts/packaging_runtime.py"),
                      str(source), str(base), action, task], base)
    return json.loads(result.stdout)


def fresh_action(action: str, task: str) -> dict:
    api = InstalledAPI()
    row = next((row for row in api.manager.list_plugins() if row["name"] == NAME), None)
    if action == "show":
        return api.outcome("outcome_show", task)["view"]
    if action == "broken":
        require(row is not None and row["error"] and row["tools"] == 0, "failed registration not isolated")
    else:
        require(row is None or not row["enabled"], "removed plugin still enabled")
    root = api.create()
    api.complete(root)
    return api.call("kanban_show", task_id=task, board="phase0")


def install_checks(cli: list[str], directory: Path, pin: str, base: Path) -> Path:
    installed = command(cli + ["plugins", "install", directory.as_uri(), "--ref", pin, "--enable"], base)
    require("skipping dependency install" in installed.stdout and "Cannot enable" in installed.stdout,
            "non-interactive dependency consent was bypassed")
    home = Path(os.environ["HERMES_HOME"])
    from hermes_cli.config import load_config_readonly
    require(NAME not in load_config_readonly()["plugins"]["enabled"], "declined plugin enabled")
    target = home / "plugins" / NAME
    metadata = json.loads((target.parent / ".install-metadata.json").read_text())[NAME]
    require(metadata["revision"] == pin and metadata["pinned"], "native source pin not recorded")
    require(all((target / name).read_bytes() == (directory / name).read_bytes()
                for name in ("plugin.yaml", "__init__.py", "hermes_outcome_loop/records.py")), "installed source differs")
    enabled = command(cli + ["plugins", "enable", NAME], base)
    require("enabled" in enabled.stdout, "native enable failed")
    require(NAME in load_config_readonly()["plugins"]["enabled"], "native selection not visible")
    from pm.environments import runtime_facts_path, selected_venv
    facts = json.loads(runtime_facts_path(Path(os.environ["HERMES_PHASE0_SOURCE"])).read_text())
    require("venv" in facts["packages"] and selected_venv(Path(os.environ["HERMES_PHASE0_SOURCE"])).is_relative_to(base),
            "PM did not select a disposable admitted dependency generation")
    command(cli + ["plugins", "doctor", str(target), "--ci"], base)
    command(cli + ["plugins", "validate", str(target), "--json"], base)
    return target


def clear_index_metadata(base: Path) -> int:
    """Force missing index metadata in this disposable seed, retaining wheel bytes."""
    cache = base / "host-home/.hermes/cache/uv"
    require(cache.resolve(strict=True).is_relative_to(base.resolve(strict=True)), "cache metadata escaped disposable root")
    entries = [entry for entry in cache.iterdir() if entry.name.startswith(("simple-v", "flat-index-v"))]
    for entry in entries:
        require(not entry.is_symlink() and entry.is_dir(), "cache metadata escaped disposable root")
    for entry in entries:
        shutil.rmtree(entry)
    return len(entries)


def failure_and_removal(cli: list[str], target: Path, task: str, view: dict, source: Path, base: Path) -> None:
    before = snapshot(base, task)
    schema = target / "schemas/common.schema.json"
    contents = schema.read_bytes()
    schema.unlink()  # Corrupt only this disposable installed copy, never source/Hermes.
    try:
        require(fresh(source, base, "broken", task)["task"]["status"] == "done", "broken registration lost delivery")
    finally:
        schema.write_bytes(contents)
    require(fresh(source, base, "show", task) == view, "fresh installed reconstruction differs")
    require(clear_index_metadata(base) > 0, "backend index cache regression was not exercised")
    command(cli + ["plugins", "disable", NAME], base)
    require(fresh(source, base, "disabled", task)["task"]["status"] == "done", "disable lost native records")
    command(cli + ["plugins", "remove", NAME], base)
    require(not target.exists(), "native removal left plugin")
    require(NAME not in json.loads((target.parent / ".install-metadata.json").read_text()), "native metadata survived removal")
    require(fresh(source, base, "removed", task)["task"]["status"] == "done", "removal lost native records")
    require(preserved(before, snapshot(base, task), 0), "disable/removal altered outcome/delivery history")


def main() -> None:
    source, base = Path(sys.argv[1]), Path(sys.argv[2]).resolve(strict=True)
    validate_paths(base)
    sys.path.insert(0, str(source))
    if len(sys.argv) > 3:
        print(json.dumps(fresh_action(sys.argv[3], sys.argv[4]), sort_keys=True))
        return
    require(base == Path("/scratch/outcome-phase0-native-packaging"), "PM seed identity mismatch")
    home = base / "host-home/.hermes"
    for name in ("tools", "cache", "installs"):
        shutil.copytree(Path("/provision/packaging-seed") / name, home / name, symlinks=True)
    archive = build(ROOT, base / "distribution")
    directory = archive.parent / NAME
    from tools.plugin_guard import scan_plugin
    scan = scan_plugin(directory, source="disposable distribution")
    require(scan.verdict == "safe", "distribution requires unresolved security scan consent")
    pin = git_distribution(directory, base)
    cli = [sys.executable, "-B", "-m", "hermes_cli.main"]
    target = install_checks(cli, directory, pin, base)
    api = InstalledAPI()
    row = next(row for row in api.manager.list_plugins() if row["name"] == NAME)
    require(row["enabled"] and not row["error"] and row["tools"] == 4 and row["hooks"] == 0, "distribution registration failed")
    task, view = workflow(api, base)
    failure_and_removal(cli, target, task, view, source, base)
    print(json.dumps({key: True for key in ("native_scan", "installed_disabled", "dependency_consent_declined",
                                          "pm_admitted", "registered_four_tools", "exercised_workflow",
                                          "failed_registration_isolated", "backend_index_cache_removed",
                                          "removal_preserves_history")}, sort_keys=True))


if __name__ == "__main__":
    main()
