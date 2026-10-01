# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable feasibility fixture, NOT the outcome plugin.

Setup/completion tools are permitted only in this test fixture. The eventual
outcome adapter remains restricted to kanban_show and kanban_comment.
"""
import json
from collections import Counter
import os
from pathlib import Path
import re
import threading
import time

ALLOWED = {"kanban_create", "kanban_complete", "kanban_show", "kanban_comment"}


def safe_dispatch(ctx, operation, arguments):
    """Experimental board/record admission policy, not a native capability claim."""
    pinned = os.environ.get("HERMES_KANBAN_BOARD")
    if os.environ.get("HERMES_KANBAN_TASK") and arguments.get("board") != pinned:
        return json.dumps({"error": "fixture refuses mismatched worker board"})
    return ctx.dispatch_tool(operation, arguments)


def bounded_append(ctx, arguments):
    """Reject before write; refuse acknowledgment when native redaction changes data."""
    body = arguments["body"]
    if len(body.encode("utf-8")) > 16384:
        return json.dumps({"error": "fixture record limit"})
    # Native forced text redaction is not a URL-query credential scrubber.
    if re.search(r"[?&](?:token|access_token|api_key|password|signature)=", body, re.IGNORECASE):
        return json.dumps({"error": "fixture rejects credential-bearing evidence URL"})
    target = {key: arguments[key] for key in ("task_id", "board")}
    before = json.loads(safe_dispatch(ctx, "kanban_show", target))
    if "error" in before:
        return json.dumps(before)
    counts = Counter(comment["body"] for comment in before["comments"])
    reply = json.loads(safe_dispatch(ctx, "kanban_comment", arguments))
    if "error" in reply:
        return json.dumps(reply)
    stored = json.loads(safe_dispatch(ctx, "kanban_show", target))
    if "error" in stored:
        return json.dumps(stored)
    added = Counter(comment["body"] for comment in stored["comments"]) - counts
    if added != Counter({body: 1}):
        return json.dumps({"error": "stored record changed; no success acknowledgment"})
    try:
        json.loads(body.split("\n", 1)[1])
    except (IndexError, ValueError):
        return json.dumps({"error": "stored record is not parseable probe JSON"})
    return json.dumps({"ok": True, "exact_stored_readback": True})


def worker_check(ctx, params):
    """Exercise authentic dispatcher pins, native sibling fence and pinned DB routing."""
    task_id = os.environ["HERMES_KANBAN_TASK"]
    board = os.environ["HERMES_KANBAN_BOARD"]
    root = Path(os.environ["HOME"]).parent.resolve()
    for key in ("HERMES_HOME", "HERMES_KANBAN_DB", "HERMES_KANBAN_WORKSPACE"):
        if not Path(os.environ[key]).resolve().is_relative_to(root):
            raise RuntimeError("worker isolation path escaped")
    state = json.loads(ctx.dispatch_tool("kanban_show", {}))
    if state["task"]["id"] != task_id or state["task"]["status"] != "running":
        raise RuntimeError("worker did not read its genuinely claimed task")
    if state["task"]["current_run_id"] != int(os.environ["HERMES_KANBAN_RUN_ID"]):
        raise RuntimeError("dispatcher run pin mismatch")
    sibling = {"task_id": params["sibling"], "board": board}
    refused = json.loads(ctx.dispatch_tool("kanban_complete", {**sibling, "summary": "must refuse"}))
    if "scoped to task" not in refused.get("error", "") or "refusing to mutate" not in refused["error"]:
        raise RuntimeError("native sibling lifecycle fence failed")
    # Native DB pin wins over mismatched board slug; it does not reject the slug.
    alias = json.loads(ctx.dispatch_tool("kanban_show", {"task_id": task_id, "board": "other"}))
    if alias["task"]["id"] != task_id:
        raise RuntimeError("native worker DB pin did not hold")
    cross = json.loads(ctx.dispatch_tool("kanban_show", {"task_id": params["other"], "board": "other"}))
    if "error" not in cross:
        raise RuntimeError("worker escaped pinned board")
    guarded = json.loads(safe_dispatch(ctx, "kanban_comment", {
        "task_id": task_id, "board": "other", "body": "must not write"}))
    if "error" not in guarded:
        raise RuntimeError("fixture explicit board guard failed")
    appended = json.loads(safe_dispatch(ctx, "kanban_comment", {
        **sibling, "body": "worker cross-task information, no lifecycle control"}))
    if "error" in appended:
        raise RuntimeError("native informational sibling append failed")
    done = json.loads(ctx.dispatch_tool("kanban_complete", {
        "task_id": task_id, "board": board, "summary": "Disposable worker fence probe"}))
    if "error" in done:
        raise RuntimeError("worker completion failed")
    report = {"passed": True, "profile": ctx.profile_name,
                       "native_task_fence": True, "native_db_pin": True,
                       "mismatched_slug_aliases_pinned_board": True,
                       "fixture_explicit_board_guard": True,
                       "sibling_information_append": True}
    persisted = json.loads(ctx.dispatch_tool("kanban_comment", {
        "task_id": task_id, "board": board, "body": "[phase0-worker]\n" + json.dumps(report)}))
    if "error" in persisted:
        raise RuntimeError("worker report persistence failed")
    return json.dumps(report)


def register(ctx):
    """Register a real dispatch probe and post-commit observer."""
    observations = []
    mode = {"value": "normal"}

    def dispatch(params, **kwargs):
        del kwargs
        operation = params["operation"]
        if operation == "observations":
            return json.dumps({"observations": observations})
        if operation == "observer_mode":
            mode["value"] = params["arguments"]["mode"]
            return json.dumps({"ok": True})
        if operation == "bounded_append":
            return bounded_append(ctx, params["arguments"])
        if operation == "safe_dispatch":
            args = params["arguments"]
            return safe_dispatch(ctx, args["operation"], args["arguments"])
        if operation not in ALLOWED:
            return json.dumps({"error": "operation outside fixture allowlist"})
        return ctx.dispatch_tool(operation, params["arguments"])

    ctx.register_tool(
        name="phase0_dispatch",
        toolset="phase0_probe",
        schema={
            "name": "phase0_dispatch",
            "description": "Disposable native interface feasibility probe",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["operation", "arguments"],
            },
        },
        handler=dispatch,
    )

    ctx.register_tool(name="phase0_worker_check", toolset="phase0_probe", schema={
        "name": "phase0_worker_check", "description": "Disposable real-worker fence checks",
        "parameters": {"type": "object", "properties": {
            "sibling": {"type": "string"}, "other": {"type": "string"}},
            "required": ["sibling", "other"]}}, handler=lambda params, **kw: worker_check(ctx, params))

    def completed(task_id, board, **kwargs):
        del kwargs
        state = json.loads(ctx.dispatch_tool(
            "kanban_show", {"task_id": task_id, "board": board}))
        if "error" in state:
            observations.append({"mode": "board-mismatch", "read_error": True,
                                 "profile": ctx.profile_name})
            return
        item = {
            "status": state["task"]["status"],
            "has_completed_event": any(
                event["kind"] == "completed" for event in state["events"]),
            "has_completed_run": any(
                run["outcome"] == "completed" for run in state["runs"]),
            "profile": ctx.profile_name,
            "mode": mode["value"],
        }
        observations.append(item)
        if mode["value"] == "error":
            raise RuntimeError("intentional disposable observer error")
        if mode["value"] == "slow":
            responses = []
            thread = threading.Thread(target=lambda: responses.append(json.loads(ctx.dispatch_tool(
                "kanban_comment", {"task_id": task_id, "board": board,
                                   "body": "parallel write while observer is slow"}))))
            thread.start()
            time.sleep(0.2)
            thread.join(timeout=2)
            item["parallel_write_finished"] = not thread.is_alive() and bool(responses) and "error" not in responses[0]

    def later_observer(**kwargs):
        del kwargs
        observations[-1]["later_observer_ran"] = True

    def track_worker(worker_pid, **kwargs):
        del kwargs
        # Disposable harness cleanup receipt only; not outcome persistence.
        root = Path(os.environ["HOME"]).parent.resolve()
        with (root / "worker-pids.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps({"pid": worker_pid}) + "\n")

    ctx.register_hook("kanban_task_completed", completed)
    ctx.register_hook("kanban_task_completed", later_observer)
    ctx.register_hook("on_kanban_worker_spawned", track_worker)
