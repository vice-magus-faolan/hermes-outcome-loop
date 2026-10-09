#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inner native checks and fresh-process operations. Source is never installed live."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from native_probe import ROOT, install_fixture, validate_paths
from phase0_runtime import require
from phase0_snapshot import snapshot, preserved
from docker_acceptance import HERMES_SHA


class NativeInterface:
    """Real scoped registry dispatch; test fixture forwards to public ctx.dispatch_tool."""

    def __init__(self, source: Path, base: Path):
        validate_paths(base)
        sys.path.insert(0, str(source))
        from hermes_cli.plugins import get_plugin_manager
        from tools.registry import registry
        import tools.kanban_tools  # noqa: F401
        self.manager = get_plugin_manager()
        self.manager.discover_and_load()
        self.registry = registry
        self.base, self.source = base, source

    def call(self, name: str, arguments: dict, allow_error: bool = False) -> dict:
        raw = self.registry.dispatch(name, arguments, scope=self.manager.scope_key)
        require(isinstance(raw, str), "native registry returned non-string result")
        result = json.loads(raw) if isinstance(raw, str) else raw
        require(allow_error or "error" not in result, "native operation failed: " + name)
        return result

    def native(self, name: str, **arguments) -> dict:
        return self.call("native_test_dispatch", {"operation": name, "arguments": arguments})

    def create(self) -> str:
        return self.native("kanban_create", title="Disposable production-native acceptance",
                           assignee="phase0-a", board="phase0", completion_contract="local-only")["task_id"]

    def complete(self, task: str) -> None:
        self.native("kanban_complete", task_id=task, board="phase0", summary="Disposable native completion")
        require(self.native("kanban_show", task_id=task, board="phase0")["task"]["status"] == "done",
                "native completion not visible")

    def payload(self, name: str, task: str) -> dict:
        value = copy.deepcopy(json.loads((ROOT / "tests/fixtures/outcome/golden.json").read_text())[name])
        value.pop("payload_sha256")
        value.update(board="phase0", task_id=task)
        if value["type"] == "observation":
            value["observed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return value

    def outcome(self, name: str, task: str, payload: dict | None = None) -> dict:
        arguments: dict = {"board": "phase0", "task_id": task}
        if payload is not None:
            arguments["contract" if name == "outcome_define" else "observation"] = payload
        return self.call(name, arguments, allow_error=True)

    def reopen(self, task: str, action: str, profile: str, payload: dict | None = None,
               enabled: bool = True, reuse_profile: bool = False) -> dict:
        env = install_fixture(self.base, profile, enabled, reuse_profile)
        args = [sys.executable, "-B", str(ROOT / "scripts/native_runtime.py"), str(self.source),
                str(self.base), task, action, json.dumps(payload)]
        result = subprocess.run(args, env=env, cwd=self.base, capture_output=True, text=True, timeout=40)
        require(result.returncode == 0, "fresh native process failed: " + action)
        return json.loads(result.stdout)


def delivered_cases(api: NativeInterface) -> dict:
    """All result fixtures use post-delivery timestamps, not old golden dates."""
    task = api.create()
    contract = api.payload("contract", task)
    require(api.outcome("outcome_define", task, contract)["ok"], "native define failed")
    require(api.outcome("outcome_show", task)["view"]["state"] == "planned", "open definition not planned")
    before_reject = snapshot(api.base, task)
    rejected = api.outcome("outcome_observe", task, api.payload("confirmed", task))
    require(rejected["error"] == "unfinished_task", "unfinished native observation admitted")
    require(preserved(before_reject, snapshot(api.base, task), 0), "unfinished rejection mutated native data")
    install_fixture(api.base, "phase0-b")
    api.native("kanban_request_review", task_id=task, board="phase0", reviewer="phase0-b",
               summary="Disposable builder handoff")
    require(api.native("kanban_show", task_id=task, board="phase0")["task"]["status"] == "review",
            "native review transition missing")
    api.reopen(task, "complete", "phase0-b", reuse_profile=True)
    before = snapshot(api.base, task)
    require(any(row["kind"] == "review_requested" for row in before["events"]), "review event missing")
    require(any(row["outcome"] == "completed" for row in before["runs"]), "native completion run missing")
    retry = api.outcome("outcome_define", task, contract)
    require(retry["acknowledgment"] == "identical_retry", "native definition retry appended")
    confirmed = api.payload("confirmed", task)
    require(api.outcome("outcome_observe", task, confirmed)["view"]["state"] == "confirmed", "native confirmation failed")
    require(api.outcome("outcome_check", task)["view"]["action"] == "NO_ACTION_REQUIRED", "confirmed action drift")
    regressed = api.payload("regressed", task)
    require(api.outcome("outcome_observe", task, regressed)["view"]["state"] == "regressed", "genuine native regression failed")
    require(api.outcome("outcome_observe", task, confirmed)["acknowledgment"] == "identical_retry", "old observation retry appended")
    require(preserved(before, snapshot(api.base, task), 2), "native delivery provenance changed")
    comments = api.native("kanban_show", task_id=task, board="phase0")["comments"]
    expected = api.outcome("outcome_show", task)["view"]
    for profile in ("phase0-restart-a", "phase0-restart-b"):
        actual = api.reopen(task, "show", profile)
        require(actual["view"] == expected and actual["comments"] == comments, "profile/restart history diverged")
    for name in ("partial", "failed", "inconclusive"):
        root = api.create()
        definition = api.payload("partial_contract" if name == "partial" else "contract", root)
        require(api.outcome("outcome_define", root, definition)["ok"], "result contract failed")
        api.complete(root)
        baseline = snapshot(api.base, root)
        observation = api.payload(name, root)
        reply = api.outcome("outcome_observe", root, observation)
        require(reply["ok"] and reply["view"]["state"] == observation["result"], "native result failed")
        require(preserved(baseline, snapshot(api.base, root), 1), "result changed delivery history")
    return {"define_view_results_regression": True, "unfinished_rejected": True,
            "native_review_completion_preserved": True, "restart_profiles_identical": True,
            "stable_retry_no_write": True}


def fresh_action(api: NativeInterface, task: str, action: str, value: dict | None) -> dict:
    """Isolated process-level readers/reviewers, not alternate outcome persistence."""
    if action == "show":
        return {"view": api.outcome("outcome_show", task)["view"],
                "comments": api.native("kanban_show", task_id=task, board="phase0")["comments"]}
    if action == "complete":
        require(api.native("kanban_show", task_id=task, board="phase0")["task"]["status"] == "review", "native review not visible")
        api.complete(task)
        return {"completed": True}
    if action == "race":
        api.call("native_test_control", {"mode": "race"})
        return api.outcome("outcome_observe", task, value)
    if action == "disabled":
        missing = api.call("outcome_show", {"board": "phase0", "task_id": task}, allow_error=True)
        require("error" in missing, "production plugin unexpectedly enabled")
        for name, arguments in (("kanban_request_review", {"summary": "Disabled plugin review"}),
                                ("kanban_complete", {"summary": "Disabled plugin completion"})):
            api.call(name, {"board": "phase0", "task_id": task, **arguments})
        state = api.call("kanban_show", {"board": "phase0", "task_id": task})
        require(state["task"]["status"] == "done", "disabled plugin blocked native work")
        return {"completed": True}
    raise RuntimeError("unknown fresh action")


def main() -> None:
    source, base = Path(sys.argv[1]), Path(sys.argv[2]).resolve(strict=True)
    api = NativeInterface(source, base)
    if len(sys.argv) > 3:
        print(json.dumps(fresh_action(api, sys.argv[3], sys.argv[4], json.loads(sys.argv[5]))))
        return
    from native_cases import failure_cases, race_cases
    report = {"hermes_sha": HERMES_SHA, **delivered_cases(api), **failure_cases(api), **race_cases(api)}
    require(not api.manager.has_hook("kanban_task_completed"), "test loader unexpectedly registered completion hook")
    report["no_completion_hook_dependency"] = True
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
