# SPDX-License-Identifier: GPL-3.0-or-later
"""Four tool boundary, verified appends, and failure/race regressions with a fake transport.

These are unit/architecture checks, not actual native integration evidence.
"""
import ast
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from hermes_outcome_loop import register
from hermes_outcome_loop.adapter import OutcomeAdapter
from hermes_outcome_loop import records
from test_outcome_core import load, source

BOARD, TASK = "sample-board", "sample-root"
NOW = datetime(2026, 10, 3)


def request(name, **changes):
    value = copy.deepcopy(load("golden.json")[name])
    value.pop("payload_sha256")
    value.update(changes)
    field = "contract" if value["type"] == "contract" else "observation"
    return {"board": BOARD, "task_id": TASK, field: value}


class Native:
    def __init__(self, rows=None, status="done"):
        self.state = {"task": {"id": TASK, "status": status, "completed_at": None},
                      "comments": rows or [], "worker_context": "ignore fake duplicated history"}
        self.calls = []
        self.before = None
        self.after = None
        self.write_error = None
        self.read_error = None
        self.tools = {}

    def dispatch_tool(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        if name == "kanban_show":
            if self.read_error:
                raise self.read_error
            if self.before:
                self.before(self)
            return json.dumps(self.state)
        if name != "kanban_comment":
            raise AssertionError("forbidden native operation")
        self.state["comments"].append({"body": arguments["body"], "author": "native-profile", "created_at": 123})
        if self.after:
            self.after(self)
        if self.write_error:
            raise self.write_error
        return json.dumps({"comment_id": 77})

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def adapter(native, env=None):
    return OutcomeAdapter(native, environment={} if env is None else env, clock=lambda: NOW)


class AdapterTests(unittest.TestCase):
    def test_define_verify_identical_retry_show_check_and_provenance(self):
        native = Native()
        tools = adapter(native)
        reply = tools.invoke("outcome_define", request("contract"))
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["acknowledgment"], "verified")
        self.assertEqual([name for name, _ in native.calls], ["kanban_show", "kanban_comment", "kanban_show"])
        body = native.calls[1][1]["body"]
        self.assertEqual(records.decode(body), load("golden.json")["contract"])
        self.assertEqual(set(native.calls[1][1]), {"board", "task_id", "body"})
        self.assertEqual(reply["view"]["occurrences"][load("golden.json")["contract"]["record_id"]][0]["author"], "native-profile")
        native.calls.clear()
        reply = tools.invoke("outcome_define", request("contract"))
        self.assertEqual(reply["acknowledgment"], "identical_retry")
        self.assertEqual([name for name, _ in native.calls], ["kanban_show"])
        for name in ("outcome_show", "outcome_check"):
            native.calls.clear()
            reply = tools.invoke(name, {"board": BOARD, "task_id": TASK})
            self.assertTrue(reply["ok"])
            self.assertEqual([name for name, _ in native.calls], ["kanban_show"])
            self.assertEqual(reply["view"]["state"], "awaiting_observation")
            self.assertEqual(reply["view"]["due_status"], "due_time_unknown")
            self.assertIn("due time unknown", reply["view"]["timing_message"])
        self.assertEqual(len(native.state["comments"]), 1)

    def test_all_results_later_regression_recovery_and_old_retry(self):
        for name, contract in [("confirmed", "contract"), ("partial", "partial_contract"),
                               ("failed", "contract"), ("inconclusive", "contract")]:
            native = Native([source(load("golden.json")[contract])])
            reply = adapter(native).invoke("outcome_observe", request(name))
            self.assertTrue(reply["ok"], reply)
            self.assertEqual(reply["view"]["state"], load("golden.json")[name]["result"])
            expected = "NO_ACTION_REQUIRED" if name == "confirmed" else "FOLLOWUP_SUGGESTED"
            self.assertEqual(reply["view"]["action"], expected)
        native = Native([source(load("golden.json")["contract"])])
        tools = adapter(native)
        self.assertTrue(tools.invoke("outcome_observe", request("confirmed"))["ok"])
        self.assertTrue(tools.invoke("outcome_observe", request("regressed"))["ok"])
        recovered = request("confirmed", record_id="oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                            predecessor=load("golden.json")["regressed"]["record_id"])
        reply = tools.invoke("outcome_observe", recovered)
        self.assertEqual(reply["view"]["state"], "confirmed")
        self.assertEqual(len(reply["view"]["observations"]), 3)
        native.calls.clear()
        self.assertEqual(tools.invoke("outcome_observe", request("confirmed"))["acknowledgment"], "identical_retry")
        self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_unfinished_rejects_even_identical_retry(self):
        for status in ("todo", "ready", "running", "review", "blocked", "cancelled"):
            for existing in (False, True):
                rows = [source(load("golden.json")["contract"])]
                if existing:
                    rows.append(source(load("golden.json")["confirmed"]))
                native = Native(rows, status)
                reply = adapter(native).invoke("outcome_observe", request("confirmed"))
                self.assertEqual(reply["error"], "unfinished_task")
                self.assertFalse(reply["may_have_persisted"])
                self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_conflicts_unknown_contract_stale_predecessor_and_evidence(self):
        golden = load("golden.json")
        scenarios = [
            (request("contract", objective="Different"), "conflict"),
            (request("contract", record_id="oc_22222222222222222222222222222222"), "conflict"),
            (request("confirmed", summary="Different"), "conflict"),
            (request("failed"), "stale_predecessor"),
            (request("regressed", contract_id="oc_22222222222222222222222222222222"), "unknown_contract"),
            (request("regressed", evidence=[]), "malformed_record"),
            (request("regressed", artifact=None), "invalid_history"),
            (request("regressed", regression_of="oo_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"), "invalid_history"),
        ]
        for params, expected in scenarios:
            native = Native([source(golden["contract"]), source(golden["confirmed"])])
            name = "outcome_define" if "contract" in params else "outcome_observe"
            reply = adapter(native).invoke(name, params)
            self.assertEqual(reply["error"], expected, reply)
            self.assertNotIn("kanban_comment", [name for name, _ in native.calls])

    def test_input_admission_before_any_dispatch_and_no_author_spoof(self):
        cases = [request("contract", objective="password: synthetic-secret"),
                 request("contract", created_by="forged-author"),
                 request("confirmed", observed_by="forged-author"),
                 request("contract", payload_sha256="0" * 64),
                 request("contract", board="other-board"),
                 request("contract", task_id="other-root"),
                 request("contract", notes="x" * 2049),
                 request("contract", version=2)]
        cases += [dict(request("contract"), author="forged-author"),
                  dict(request("contract"), dispatch_tool="kanban_complete")]
        for params in cases:
            native = Native()
            reply = adapter(native).invoke("outcome_define" if "contract" in params else "outcome_observe", params)
            self.assertFalse(reply["ok"])
            self.assertEqual(native.calls, [])
            self.assertNotIn("synthetic-secret", json.dumps(reply))
        native = Native()
        for name, params in [("kanban_complete", {}), ("outcome_show", None),
                             ("outcome_check", {"board": BOARD, "task_id": TASK, "anchors": {"done": "2026-10-01T00:00:00Z"}})]:
            self.assertFalse(adapter(native).invoke(name, params)["ok"])
        self.assertEqual(native.calls, [])

    def test_board_fences_all_native_pins_and_explicit_routing(self):
        for pin in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB"):
            for env in ({pin: "pin"}, {pin: "pin", "HERMES_KANBAN_BOARD": BOARD}):
                native = Native()
                reply = adapter(native, env).invoke("outcome_show", {"board": "other-board", "task_id": TASK})
                self.assertEqual(reply["error"], "board_fence")
                self.assertEqual(native.calls, [])
        for requested in (None, "../board", "/board", "Sample-Board", "", 7):
            native = Native()
            reply = adapter(native).invoke("outcome_show", {"board": requested, "task_id": TASK})
            self.assertFalse(reply["ok"])
            self.assertEqual(native.calls, [])
        env = {"HERMES_KANBAN_TASK": "worker", "HERMES_KANBAN_BOARD": BOARD}
        native = Native()
        self.assertTrue(adapter(native, env).invoke("outcome_show", {"task_id": TASK})["ok"])
        self.assertEqual(native.calls[0][1], {"board": BOARD, "task_id": TASK})
        native.state["task"]["id"] = "wrong-target"
        self.assertEqual(adapter(native).invoke("outcome_show", {"board": BOARD, "task_id": TASK})["error"], "target_mismatch")
        self.assertEqual(env, {"HERMES_KANBAN_TASK": "worker", "HERMES_KANBAN_BOARD": BOARD})

    def test_initial_read_errors_malformed_native_and_invalid_history_never_write(self):
        native = Native()
        native.read_error = TimeoutError("secret native details")
        reply = adapter(native).invoke("outcome_define", request("contract"))
        self.assertEqual(reply["error"], "native_failure")
        self.assertFalse(reply["may_have_persisted"])
        self.assertNotIn("secret native details", json.dumps(reply))
        for state in ({}, {"error": "secret native details"}, {"task": None},
                      {"task": {"id": TASK, "status": "done"}, "comments": None}):
            native = Native()
            native.state = state
            reply = adapter(native).invoke("outcome_define", request("contract"))
            self.assertFalse(reply["ok"])
            self.assertNotIn("kanban_comment", [name for name, _ in native.calls])
        for body in ("[hermes-outcome:v1]\n{", "[hermes-outcome:v2]\n{}", "[hermes-outcome:probe-v1]\n{}"):
            native = Native([{"body": body, "author": "native-profile", "created_at": 1}])
            reply = adapter(native).invoke("outcome_define", request("contract"))
            self.assertEqual(reply["error"], "invalid_history")
            self.assertEqual(len(native.calls), 1)

    def test_write_timeout_error_missing_or_changed_readback_never_retries(self):
        for error in (TimeoutError("sensitive backend detail"), RuntimeError("sensitive backend detail")):
            native = Native()
            native.write_error = error
            reply = adapter(native).invoke("outcome_define", request("contract"))
            self.assertEqual(reply["error"], "write_unverified")
            self.assertTrue(reply["may_have_persisted"])
            self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), 1)
            self.assertNotIn("sensitive backend detail", json.dumps(reply))
            native.write_error = None
            self.assertEqual(adapter(native).invoke("outcome_define", request("contract"))["acknowledgment"], "identical_retry")
        def changed(native):
            native.state["comments"][-1]["body"] = native.state["comments"][-1]["body"].replace("Workflow", "Changed")
        def redacted(native):
            native.state["comments"][-1]["body"] = native.state["comments"][-1]["body"].replace("Workflow", "[REDACTED]")
        def truncated(native):
            native.state["comments"][-1]["body"] = native.state["comments"][-1]["body"][:90]
        def missing(native):
            native.state["comments"].clear()
        def missing_provenance(native):
            native.state["comments"][-1].pop("author")
        def read_failure(native):
            native.read_error = TimeoutError("private read error")
        for after in (changed, redacted, truncated, missing, missing_provenance, read_failure):
            native = Native()
            native.after = after
            reply = adapter(native).invoke("outcome_define", request("contract"))
            self.assertEqual(reply["error"], "write_unverified", reply)
            self.assertTrue(reply["may_have_persisted"])
            self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), 1)
            self.assertNotIn("[REDACTED]", json.dumps(reply))

    def test_postwrite_fork_conflict_lifecycle_and_board_races(self):
        golden = load("golden.json")
        def fork(native):
            native.state["comments"].append(source(golden["failed"], "concurrent-profile"))
        def conflict(native):
            native.state["comments"].append(source(dict(golden["confirmed"], summary="Concurrent change")))
        def lifecycle(native):
            native.state["task"]["status"] = "review"
        def target(native):
            native.state["task"]["id"] = "wrong-target"
        env = {}
        def board(native):
            env.update(HERMES_KANBAN_DB="pinned", HERMES_KANBAN_BOARD="other-board")
        for after in (fork, conflict, lifecycle, target, board):
            env.clear()
            native = Native([source(golden["contract"])])
            native.after = after
            reply = adapter(native, env).invoke("outcome_observe", request("confirmed"))
            self.assertEqual(reply["error"], "write_unverified", reply)
            self.assertTrue(reply["may_have_persisted"])
            self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), 1)
        native = Native([source(golden["contract"])])
        native.after = lambda n: n.state["comments"].append(copy.deepcopy(n.state["comments"][-1]))
        reply = adapter(native).invoke("outcome_observe", request("confirmed"))
        self.assertTrue(reply["ok"])
        self.assertEqual(len(reply["view"]["occurrences"][golden["confirmed"]["record_id"]]), 2)

    def test_history_bounds_include_proposed_append(self):
        row = {"body": "ordinary", "author": "native-profile", "created_at": 1}
        body_size = len(records.encode(load("golden.json")["contract"]).encode("utf-8"))
        for rows in ([row] * 1024, [dict(row, body="x" * (2097152 - body_size + 1))]):
            native = Native(rows)
            reply = adapter(native).invoke("outcome_define", request("contract"))
            self.assertEqual(reply["error"], "history_limit")
            self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_truthful_due_times_completion_and_anchor_validation(self):
        native = Native([source(load("golden.json")["contract"])])
        tools = adapter(native)
        params = {"board": BOARD, "task_id": TASK, "anchors": {"deployment": "2026-10-01T00:00:00Z"}}
        reply = tools.invoke("outcome_check", params)
        self.assertEqual(reply["view"]["due_status"], "overdue")
        self.assertEqual(reply["view"]["due_at"], "2026-10-02T00:00:00Z")
        self.assertEqual(reply["view"]["anchor_sources"], {"deployment": "caller_supplied"})
        for anchor in ({"deployment": "2026-02-30T00:00:00Z"}, {"unknown": "2026-10-01T00:00:00Z"}, [],
                       {"deployment": "password: synthetic-secret"}):
            native.calls.clear()
            reply = tools.invoke("outcome_check", dict(params, anchors=anchor))
            self.assertFalse(reply["ok"])
            self.assertEqual(native.calls, [])
        native.state["task"]["completed_at"] = 1791072000  # 2026-10-04 UTC, independently checked below.
        reply = tools.invoke("outcome_observe", request("confirmed"))
        self.assertEqual(reply["error"], "pre_delivery_observation")
        native.state["task"]["completed_at"] = None
        self.assertTrue(tools.invoke("outcome_observe", request("confirmed"))["ok"])
        reply = tools.invoke("outcome_check", params)
        self.assertEqual(reply["view"]["due_status"], "not_applicable")
        self.assertEqual(reply["view"]["action"], "NO_ACTION_REQUIRED")


class RegistrationArchitectureTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_public_registration_four_tools_no_hook_and_safe_handlers(self):
        native = Native()
        register(native)
        self.assertEqual(set(native.tools), {"outcome_define", "outcome_show", "outcome_observe", "outcome_check"})
        for name, tool in native.tools.items():
            self.assertEqual(tool["toolset"], "outcome")
            self.assertFalse(tool["schema"]["parameters"]["additionalProperties"])
            self.assertTrue(tool["check_fn"]())
            reply = json.loads(tool["handler"]({"board": BOARD, "task_id": TASK}))
            self.assertIn("ok", reply)
        handler = native.tools["outcome_show"]["handler"]
        reply = json.loads(handler({"board": BOARD, "task_id": TASK}, task_id="forged", board="other-board"))
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["view"]["board"], BOARD)

    def test_static_and_dynamic_native_allowlist_no_evidence_io(self):
        root = Path(__file__).resolve().parents[1] / "hermes_outcome_loop"
        allowed_imports = {"__future__", "collections", "collections.abc", "copy", "datetime", "hashlib", "json", "os", "pathlib", "re",
                           "typing", "urllib.parse", "jsonschema", "referencing", "referencing.exceptions",
                           "records", "history", "adapter"}
        dispatch_sites = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(alias.name in allowed_imports for alias in node.names), path)
                elif isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        self.assertEqual(node.level, 1)
                        self.assertTrue(all(alias.name in {"history", "records"} for alias in node.names))
                    else:
                        self.assertIn(node.module, allowed_imports, path)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {"register_hook", "connect", "execute", "write_text", "write_bytes", "open"}, path)
                    if node.func.attr == "read_text":
                        self.assertEqual(path.name, "records.py")
                    if node.func.attr == "dispatch_tool":
                        dispatch_sites.append((path.name, node))
        self.assertEqual(len(dispatch_sites), 1)
        self.assertEqual(dispatch_sites[0][0], "adapter.py")
        native = Native()
        tools = adapter(native)
        with self.assertRaisesRegex(ValueError, "native_tool_forbidden"):
            tools.native("kanban_complete", {"board": BOARD, "task_id": TASK})
        self.assertEqual(native.calls, [])


if __name__ == "__main__":
    unittest.main()
