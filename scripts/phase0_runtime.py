#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inner runtime probe; launched only by phase0_probe in an isolated subprocess."""
from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

MARKER = "[hermes-outcome:probe-v1]\n"


def require(condition: bool, message: str) -> None:
    """Use non-optimizable assertions for every probe prerequisite."""
    if not condition:
        raise RuntimeError(message)


def validate_isolation(base: Path) -> None:
    """Refuse any ambient path overrides before importing Hermes."""
    require(base.name.startswith("outcome-phase0-"), "not a disposable probe root")
    expected = {
        "HOME": base / "host-home",
        "HERMES_HOME": base / "host-home/.hermes/profiles/phase0-a",
        "HERMES_KANBAN_HOME": base / "board-root",
        "TMPDIR": base / "tmp",
    }
    for key, path in expected.items():
        require(Path(os.environ[key]).resolve() == path, "unsafe isolation path")
        require(path.is_relative_to(base), "isolation path escaped")
    allowed = set(expected) | {"HERMES_PROFILE", "HERMES_KANBAN_BOARD",
                              "HERMES_ENABLE_PROJECT_PLUGINS"}
    require(not any(key.startswith("HERMES_") and key not in allowed
                    for key in os.environ), "inherited runtime/worker override")
    require(not list(base.rglob("kanban.db")), "disposable board already existed")


def record(number: int, text: str = "disposable evidence") -> str:
    """Deterministic synthetic data only; never real secrets or live identifiers."""
    return MARKER + json.dumps({"record_id": f"probe_{number}", "summary": text},
                               sort_keys=True, separators=(",", ":"))


def validate_comments(comments: list[dict]) -> None:
    """Require exact roundtrip and native provenance in the four-record burst."""
    require(len(comments) == 4, "comment history incomplete")
    require([comment["body"] for comment in comments] == [record(i) for i in range(4)],
            "stored deterministic JSON changed")
    require(all(comment["author"] == "phase0-a" for comment in comments), "profile identity drift")
    require(all(isinstance(comment["created_at"], int) for comment in comments), "missing native time")


def validate_delivery_preservation(before: dict, after: dict) -> None:
    """Allow only expected native commented additions in a bounded public history."""
    require(after["task"] == before["task"] and after["runs"] == before["runs"],
            "comment append changed delivery task/run")
    require(after["events"][:len(before["events"])] == before["events"], "delivery events changed")
    additions = after["events"][len(before["events"]):]
    require(len(additions) == 4 and all(event["kind"] == "commented" for event in additions),
            "unexpected post-delivery event additions")


def history_probe(call, task_id: str) -> dict:
    """Show the ID discrepancy and preserve native completion provenance."""
    before = call("kanban_show", task_id=task_id, board="phase0")
    replies = []
    for number in range(4):
        replies.append(call("kanban_comment", task_id=task_id, board="phase0",
                            body=record(number)))
    after = call("kanban_show", task_id=task_id, board="phase0")
    comments = after["comments"]
    validate_comments(comments)
    validate_delivery_preservation(before, after)
    ids = [reply["comment_id"] for reply in replies]
    return {
        "count": len(comments), "public_comment_fields": sorted(comments[0]),
        "append_returns_distinct_monotonic_ids": ids == sorted(set(ids)),
        "read_has_native_ids": all("id" in comment for comment in comments),
        "has_same_second_ties": len({comment["created_at"] for comment in comments}) < len(comments),
        "post_done_append_and_readback": True, "native_author_and_time": True,
        "delivery_task_runs_and_existing_events_preserved": True,
        "only_new_commented_events": True,
    }


def redaction_probe(call, task_id: str) -> dict:
    """Compare synthetic sensitive-looking JSON with the actual stored body."""
    synthetic = "sk-" + "SYNTHETIC_NOT_A_SECRET_1234567890"
    original = record(10, synthetic)
    call("kanban_comment", task_id=task_id, board="phase0", body=original)
    stored = call("kanban_show", task_id=task_id, board="phase0")["comments"][-1]["body"]
    decoded = json.loads(stored.removeprefix(MARKER))
    require(synthetic not in stored, "tool failed to redact synthetic token")
    require(decoded["record_id"] == "probe_10", "redaction changed safe record ID")
    return {"synthetic_token_redacted": True, "json_remains_parseable": True,
            "safe_id_preserved": True, "stored_payload_changed": stored != original}


def size_probe(call, task_id: str) -> dict:
    """Bounded 4/16/64 KiB exploration, not an unbounded native-limit search."""
    accepted = []
    for size in (4096, 16384, 65536):
        body = record(size, "x" * size)
        call("kanban_comment", task_id=task_id, board="phase0", body=body)
        stored = call("kanban_show", task_id=task_id, board="phase0")["comments"][-1]["body"]
        require(stored == body, "native truncation or payload change")
        accepted.append(len(body.encode("utf-8")))
    before_rejection = call("kanban_show", task_id=task_id, board="phase0")
    rejected = call("kanban_comment", task_id=task_id, board="phase0", body="", allow_error=True)
    require("error" in rejected, "empty body accepted")
    after_rejection = call("kanban_show", task_id=task_id, board="phase0")
    for field in ("task", "runs", "events", "comments"):
        require(before_rejection[field] == after_rejection[field], "rejected append changed history")
    return {"accepted_record_bytes": accepted, "exact_readback": True,
            "empty_rejected": True, "native_maximum_established": False}


def timing_probe(call, task_id: str) -> dict:
    """Measure fresh public read plus deterministic-record parse on one thread."""
    elapsed = []
    state = call("kanban_show", task_id=task_id, board="phase0")
    for _ in range(20):
        start = time.perf_counter()
        state = call("kanban_show", task_id=task_id, board="phase0")
        for comment in state["comments"]:
            json.loads(comment["body"].removeprefix(MARKER))
        elapsed.append((time.perf_counter() - start) * 1000)
    return {"samples": len(elapsed), "comments": len(state["comments"]),
            "median_ms": round(statistics.median(elapsed), 3),
            "maximum_ms": round(max(elapsed), 3),
            "response_bytes": len(json.dumps(state).encode("utf-8"))}


def main() -> None:
    """Exercise actual loaded PluginContext and native tool handlers."""
    source = Path(sys.argv[1]).resolve(strict=True)
    base = Path(sys.argv[2]).resolve(strict=True)
    validate_isolation(base)
    sys.path.insert(0, str(source))
    # Embed the public plugin/tool library in the already provisioned venv.
    # CLI bootstrap can auto-provision a fresh HOME; never invoke it here.
    require(sys.prefix != sys.base_prefix, "use Hermes's provisioned dependency venv")
    from hermes_cli.plugins import get_plugin_manager
    from tools.registry import registry
    import tools.kanban_tools  # noqa: F401 - register shipped native tool schemas

    manager = get_plugin_manager()
    manager.discover_and_load()

    def call(operation: str, allow_error: bool = False, **arguments) -> dict:
        raw = registry.dispatch("phase0_dispatch", {
            "operation": operation, "arguments": arguments}, scope=manager.scope_key)
        if not isinstance(raw, str):
            raise RuntimeError("registry returned a non-string result")
        result = json.loads(raw)
        require(allow_error or "error" not in result, f"native {operation} rejected: {result.get('error')}")
        return result

    def create(board: str = "phase0", complete: bool = False) -> str:
        task = call("kanban_create", title="Disposable interface probe", assignee="phase0-a",
                    board=board, completion_contract="local-only")["task_id"]
        if complete:
            call("kanban_complete", task_id=task, board=board, summary="Disposable probe setup")
        return task

    def complete(task_id: str) -> None:
        call("kanban_complete", task_id=task_id, board="phase0",
             summary="Disposable public-interface feasibility evidence")
        state = call("kanban_show", task_id=task_id, board="phase0")
        require(state["task"]["status"] == "done", "canonical completion not visible")

    task_id = create()
    complete(task_id)
    report = {"headless_registered_plugin_dispatch": True, "isolation": True,
              "history": history_probe(call, task_id)}
    report["redaction"] = redaction_probe(call, task_id)
    report["sizes"] = size_probe(call, task_id)
    report["read_parse_cost"] = timing_probe(call, task_id)
    other = create("other", complete=True)
    require(call("kanban_show", task_id=other, board="other")["task"]["id"] == other,
            "explicit board failed")
    wrong = call("kanban_show", task_id=other, board="phase0", allow_error=True)
    require("error" in wrong, "explicit board leaked cross-board task")
    report["explicit_headless_board_routing"] = True
    report["observer"] = call("observations")["observations"]
    report["cross_board_hook_read_error"] = any(item["mode"] == "board-mismatch" for item in report["observer"])
    require(report["observer"] and all(
        item["status"] == "done" and item["has_completed_event"] and item["has_completed_run"]
        for item in report["observer"] if item["mode"] == "normal"), "observer could not read durable completion")
    report["source_sha"] = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    report["python_version"] = sys.version.split()[0]
    from hermes_cli.version_info import get_version_info
    report["installed_version"] = get_version_info().derived_version
    from phase0_extended import (ordering_probe, policy_probe, lifecycle_probe,
                                 profile_probe, scaling_probe, worker_probe, race_probe)
    from phase0_data import redaction_corpus, padded_scaling

    def completed_create(complete=True):
        return create(complete=complete)

    report["ordering"] = ordering_probe(call, completed_create)
    report["record_policy"] = policy_probe(call, completed_create)
    report["redaction_corpus"] = redaction_corpus(call, completed_create, base)
    report["lifecycle"] = lifecycle_probe(call, completed_create)
    report["profiles"] = profile_probe(call, completed_create, source, base)
    report["race"] = race_probe(call, completed_create, source, base)
    report["scaling"] = scaling_probe(call, completed_create, base)
    report["padded_scaling"] = padded_scaling(call, completed_create)
    report["worker"] = worker_probe(call, completed_create, source, base, task_id, other)
    report["gate"] = "approved logical predecessor reconstruction and all required real-runtime contexts"
    report["not_exercised"] = []
    report["feasible"] = all(report[key]["passed"] for key in
                             ("ordering", "record_policy", "redaction_corpus", "lifecycle",
                              "profiles", "race", "scaling", "padded_scaling", "worker"))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
