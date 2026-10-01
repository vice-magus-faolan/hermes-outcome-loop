# SPDX-License-Identifier: GPL-3.0-or-later
"""Narrow synchronous public-plugin adapter: read, optionally append, read back.

No hard cancellation, automatic uncertain retry, evidence I/O, lifecycle authority,
locks or persistence. Environment is read anew at every native dispatch.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import json
import os
import re
from typing import Protocol

from . import history, records
from .records import OutcomeError

NATIVE_TOOLS = frozenset({"kanban_show", "kanban_comment"})
WORKER_PINS = ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB")
INPUT_FIELDS = {
    "outcome_define": {"board", "task_id", "contract"},
    "outcome_show": {"board", "task_id"},
    "outcome_observe": {"board", "task_id", "observation"},
    "outcome_check": {"board", "task_id", "anchors"},
}


class NativeContext(Protocol):
    """Only Hermes's public dispatch capability is required at the native boundary."""
    def dispatch_tool(self, name: str, arguments: dict) -> str: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def resolve_board(requested: object, environment: Mapping[str, str]) -> str:
    pinned = any(key in environment for key in WORKER_PINS)
    ambient = environment.get("HERMES_KANBAN_BOARD")
    if pinned and (not ambient or requested not in (None, ambient)):
        raise OutcomeError("board_fence")
    board = ambient if requested is None and pinned else requested
    if not isinstance(board, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", board):
        raise OutcomeError("board_required")
    return board


def anchors_input(value: object) -> dict:
    if not isinstance(value, dict) or not set(value) <= {"integration", "deployment", "first_workflow"}:
        raise OutcomeError("invalid_anchors")
    for timestamp in value.values():
        records.timestamp(timestamp)
    return dict(value)


def inputs(name: str, params: object, environment: Mapping[str, str]) -> tuple[str, str, dict, dict | None]:
    """Admit full immutable payloads before dispatch; accept no author/override fields."""
    if name not in INPUT_FIELDS:
        raise OutcomeError("unknown_tool")
    if not isinstance(params, dict) or not set(params) <= INPUT_FIELDS[name]:
        raise OutcomeError("invalid_arguments")
    board = resolve_board(params.get("board"), environment)
    task_id = params.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", task_id):
        raise OutcomeError("task_required")
    anchors = anchors_input(params.get("anchors", {}))
    field = {"outcome_define": "contract", "outcome_observe": "observation"}.get(name)
    payload = prepare(params.get(field), field, board, task_id) if field else None
    return board, task_id, anchors, payload


def prepare(value: object, kind: str, board: str, task_id: str) -> dict:
    if not isinstance(value, dict) or "payload_sha256" in value or value.get("type") != kind:
        raise OutcomeError("malformed_record")
    record = records.seal(value)
    records.encode(record)
    if (record["board"], record["task_id"]) != (board, task_id):
        raise OutcomeError("target_mismatch")
    return record


def completion_time(task: dict) -> str | None:
    """Use native task timestamp only, never infer a missing anchor from event order."""
    value = task.get("completed_at")
    if value is None or task["status"] != "done":
        return None
    if type(value) is not int or value < 0:
        raise OutcomeError("malformed_native_response")
    try:
        return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        raise OutcomeError("malformed_native_response") from None


def native_task(reply: dict, task_id: str) -> tuple[str, str | None]:
    task = reply.get("task")
    if not isinstance(task, dict):
        raise OutcomeError("malformed_native_response")
    if task.get("id") != task_id:
        raise OutcomeError("target_mismatch")
    status = task.get("status")
    if not isinstance(status, str) or not re.fullmatch(r"[a-z][a-z_]{0,31}", status):
        raise OutcomeError("malformed_native_response")
    return status, completion_time(task)


def timing_view(view: dict, completed: str | None, anchors: dict, now: datetime) -> None:
    """Timing only applies to unobserved done delivery, not repeat cadence."""
    view.update(due_status="not_applicable", due_at=None, anchor_sources={}, timing_message=None)
    if view["state"] != "awaiting_observation":
        return
    timing = view["timing"]
    known = dict(anchors)
    sources = {key: "caller_supplied" for key in known}
    if completed is not None:
        known["done"] = completed
        sources["done"] = "native_completion"
    deadlines = []
    if timing["deadline"] is not None:
        deadlines.append(records.timestamp(timing["deadline"]))
    anchor = timing["anchor"]
    if anchor in known:
        deadlines.append(records.timestamp(known[anchor]) + timedelta(seconds=timing["delay_seconds"]))
        view["anchor_sources"] = {anchor: sources[anchor]}
    if not deadlines:
        view.update(due_status="due_time_unknown", timing_message="awaiting observation; due time unknown")
        return
    deadline = min(deadlines)
    due_status = "due" if now == deadline else ("overdue" if now > deadline else "not_due")
    view.update(due_status=due_status, due_at=deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
                timing_message=f"awaiting observation; {due_status}")


def preflight(record: dict, reply: dict, view: dict, completed: str | None) -> str:
    if record["type"] == "observation" and view["kanban_status"] != "done":
        raise OutcomeError("unfinished_task")
    if view["diagnostics"]:
        raise OutcomeError("invalid_history")
    if record["type"] == "observation" and completed is not None:
        if records.timestamp(record["observed_at"]) < records.timestamp(completed):
            raise OutcomeError("pre_delivery_observation")
    existing = view["variants"].get(record["record_id"])
    if existing:
        if existing != [record]:
            raise OutcomeError("conflict")
        return "identical_retry"
    check_identity(record, view)
    synthetic = {"body": records.encode(record), "author": "preflight-only", "created_at": 0}
    proposed = history.reconstruct(reply["comments"] + [synthetic], view["kanban_status"],
                                   record["board"], record["task_id"], completed)
    if "history_limit" in proposed["diagnostics"]:
        raise OutcomeError("history_limit")
    if proposed["diagnostics"]:
        raise OutcomeError("invalid_history")
    return "append"


def check_identity(record: dict, view: dict) -> None:
    if record["type"] == "contract":
        if view["contract"] is not None:
            raise OutcomeError("conflict")
        return
    contract = view["contract"]
    if contract is None or contract["record_id"] != record["contract_id"]:
        raise OutcomeError("unknown_contract")
    if record["predecessor"] != view["latest"]:
        raise OutcomeError("stale_predecessor")


def failure(code: str, may_have_persisted: bool = False, diagnostics: list[str] | None = None) -> dict:
    return {"ok": False, "error": code, "may_have_persisted": may_have_persisted,
            "diagnostics": diagnostics or [code]}


class OutcomeAdapter:
    """Expose four operations; inject transport/environment/clock only in host tests.

    A synchronous native call can delay its caller. No cancellable hard timeout is
    claimed. Any failed attempted append is uncertain and is never retried here.
    """
    def __init__(self, context: NativeContext, environment: Mapping[str, str] | None = None,
                 clock: Callable[[], datetime] = utc_now):
        self.context = context
        self.environment = os.environ if environment is None else environment
        self.clock = clock

    def native(self, name: str, arguments: dict) -> dict:
        """One allowlisted public dispatch site; recheck worker board every time."""
        if name not in NATIVE_TOOLS:
            raise OutcomeError("native_tool_forbidden")
        expected = {"board", "task_id", "body"} if name == "kanban_comment" else {"board", "task_id"}
        if set(arguments) != expected:
            raise OutcomeError("invalid_arguments")
        resolve_board(arguments["board"], self.environment)
        try:
            raw = self.context.dispatch_tool(name, arguments)
            value = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            raise OutcomeError("native_failure") from None
        if not isinstance(value, dict):
            raise OutcomeError("malformed_native_response")
        if "error" in value:
            raise OutcomeError("native_failure")
        return value

    def read(self, board: str, task_id: str, anchors: dict) -> tuple[dict, dict, str | None]:
        reply = self.native("kanban_show", {"board": board, "task_id": task_id})
        status, completed = native_task(reply, task_id)
        view = history.reconstruct(reply.get("comments"), status, board, task_id, completed)
        timing_view(view, completed, anchors, self.clock())
        return reply, view, completed

    def append(self, record: dict, anchors: dict) -> dict:
        """At most one attempted append, and exact persisted-body/full-history admission."""
        board, task_id = record["board"], record["task_id"]
        expected = records.encode(record)
        try:
            self.native("kanban_comment", {"board": board, "task_id": task_id, "body": expected})
            _, view, _ = self.read(board, task_id, anchors)
            sources = view["occurrences"].get(record["record_id"], [])
            if view["diagnostics"]:
                return failure("write_unverified", True, view["diagnostics"])
            if not any(row["body"] == expected for row in sources):
                return failure("write_unverified", True, ["readback_mismatch"])
            if view["variants"].get(record["record_id"]) != [record]:
                return failure("write_unverified", True, ["readback_mismatch"])
            return {"ok": True, "acknowledgment": "verified", "may_have_persisted": True, "view": view}
        except OutcomeError as error:
            return failure("write_unverified", True, [str(error)])
        except Exception:
            return failure("write_unverified", True, ["operation_failure"])

    def invoke(self, name: str, params: object) -> dict:
        """Safe tool result; rejected/native error details never reach callers."""
        try:
            board, task_id, anchors, record = inputs(name, params, self.environment)
            reply, view, completed = self.read(board, task_id, anchors)
            if record is None:
                return {"ok": True, "view": view}
            admission = preflight(record, reply, view, completed)
            if admission == "identical_retry":
                return {"ok": True, "acknowledgment": admission, "may_have_persisted": False, "view": view}
            return self.append(record, anchors)
        except OutcomeError as error:
            return failure(str(error))
        except Exception:
            return failure("operation_failure")
