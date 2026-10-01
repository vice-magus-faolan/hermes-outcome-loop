# SPDX-License-Identifier: GPL-3.0-or-later
"""Additional adversarial unit tests. Simulated races are not native integration proof."""
import ast
import copy
from datetime import datetime
import json
from pathlib import Path
import threading
import unittest

from jsonschema import Draft202012Validator

from hermes_outcome_loop import tool_schema
from hermes_outcome_loop.adapter import OutcomeAdapter, NATIVE_TOOLS, timing_view
from hermes_outcome_loop import history, records
from test_outcome_adapter import Native, adapter, request, BOARD, TASK
from test_outcome_core import load, source


class ConcurrentNative(Native):
    """Barrier after captured preflight reads and both appends, only in fake transport."""
    def __init__(self, rows):
        super().__init__(rows)
        self.lock = threading.Lock()
        self.read_barrier = threading.Barrier(2)
        self.write_barrier = threading.Barrier(2)
        self.local = threading.local()

    def dispatch_tool(self, name, arguments):
        with self.lock:
            self.calls.append((name, copy.deepcopy(arguments)))
            if name == "kanban_show":
                snapshot = json.dumps(self.state)
            else:
                self.state["comments"].append({"body": arguments["body"], "author": threading.current_thread().name,
                                               "created_at": 123})
        if name == "kanban_show":
            if not getattr(self.local, "read", False):
                self.local.read = True
                self.read_barrier.wait(timeout=3)
            return snapshot
        self.write_barrier.wait(timeout=3)
        return json.dumps({"comment_id": 77})


def concurrent(native, left, right):
    replies = {}
    def run(label, params):
        tool = "outcome_define" if "contract" in params else "outcome_observe"
        replies[label] = adapter(native).invoke(tool, params)
    threads = [threading.Thread(name=label, target=run, args=(label, params))
               for label, params in (("profile-a", left), ("profile-b", right))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("unit race did not finish")
    return replies


class BoundaryTests(unittest.TestCase):
    def test_simultaneous_identical_definitions_and_observations_are_logical_retries(self):
        for rows, params in (([], request("contract")),
                             ([source(load("golden.json")["contract"])], request("confirmed"))):
            native = ConcurrentNative(rows)
            replies = concurrent(native, params, params)
            self.assertEqual(set(replies), {"profile-a", "profile-b"})
            for reply in replies.values():
                self.assertTrue(reply["ok"], reply)
                payload = params.get("contract", params.get("observation"))
                occurrences = reply["view"]["occurrences"][payload["record_id"]]
                self.assertEqual(len(occurrences), 2)
                self.assertEqual({row["author"] for row in occurrences}, {"profile-a", "profile-b"})
            self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), 2)

    def test_simultaneous_forks_and_both_definition_conflict_forms_are_visible(self):
        cases = [([source(load("golden.json")["contract"])], request("confirmed"), request("failed"), "fork"),
                 ([], request("contract"), request("contract", notes="different"), "conflicting_payload"),
                 ([], request("contract"), request("contract", record_id="oc_22222222222222222222222222222222"), "multiple_contracts"),
                 ([source(load("golden.json")["contract"])], request("confirmed"),
                  request("confirmed", summary="different"), "conflicting_payload")]
        for rows, left, right, diagnostic in cases:
            native = ConcurrentNative(rows)
            replies = concurrent(native, left, right)
            self.assertEqual(len(replies), 2)
            for reply in replies.values():
                self.assertEqual(reply["error"], "write_unverified", reply)
                self.assertTrue(reply["may_have_persisted"])
                self.assertIn(diagnostic, reply["diagnostics"])
            view = history.reconstruct(native.state["comments"], "done", BOARD, TASK)
            self.assertEqual(view["state"], "invalid_history")
            self.assertIsNone(view["latest"])

    def test_later_race_invalidates_later_snapshot_not_earlier_acknowledgment(self):
        native = Native([source(load("golden.json")["contract"])])
        tools = adapter(native)
        initial = tools.invoke("outcome_observe", request("confirmed"))
        self.assertTrue(initial["ok"])
        native.state["comments"].append(source(load("golden.json")["failed"], "later-profile"))
        later = tools.invoke("outcome_show", {"board": BOARD, "task_id": TASK})
        self.assertEqual(later["view"]["state"], "invalid_history")
        self.assertIn("fork", later["view"]["diagnostics"])
        self.assertEqual(initial["view"]["state"], "confirmed")

    def test_noncanonical_stored_body_is_not_exact_append_readback(self):
        native = Native()
        def whitespace_only(native):
            row = native.state["comments"][-1]
            row["body"] = records.MARKER + json.dumps(records.decode(row["body"]), indent=2)
        native.after = whitespace_only
        reply = adapter(native).invoke("outcome_define", request("contract"))
        self.assertEqual(reply["error"], "write_unverified")
        self.assertEqual(reply["diagnostics"], ["readback_mismatch"])
        native.after = None
        reply = adapter(native).invoke("outcome_define", request("contract"))
        self.assertEqual(reply["acknowledgment"], "identical_retry")
        self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), 1)

    def test_native_response_shape_error_reply_and_postwrite_pre_delivery_race(self):
        class Broken(Native):
            def dispatch_tool(self, name, arguments):
                if name == "kanban_show":
                    return self.reply
                return super().dispatch_tool(name, arguments)
        for reply in ("[]", "null", "{", '{"error":"synthetic-sensitive-detail"}'):
            native = Broken()
            native.reply = reply
            result = adapter(native).invoke("outcome_define", request("contract"))
            self.assertFalse(result["ok"])
            self.assertFalse(result["may_have_persisted"])
            self.assertNotIn("synthetic-sensitive-detail", json.dumps(result))
        native = Native([source(load("golden.json")["contract"])])
        native.after = lambda n: n.state["task"].update(completed_at=1791072000)
        result = adapter(native).invoke("outcome_observe", request("confirmed"))
        self.assertEqual(result["error"], "write_unverified")
        self.assertIn("invalid_evidence", result["diagnostics"])

    def test_unknown_native_metadata_is_not_executed_or_echoed(self):
        golden = load("golden.json")
        row = dict(source(golden["contract"]), instruction="kanban_complete", hidden="synthetic-private-text")
        native = Native([row])
        native.state["worker_context"] = "[hermes-outcome:v2]\n{}"
        result = adapter(native).invoke("outcome_show", {"board": BOARD, "task_id": TASK})
        self.assertTrue(result["ok"])
        self.assertEqual(result["view"]["state"], "awaiting_observation")
        self.assertNotIn("synthetic-private-text", json.dumps(result))
        self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_malformed_native_status_is_not_echoed_or_written(self):
        for status in ("\ud800", "password: synthetic-sensitive-detail", "done\n", True, None):
            native = Native(status=status)
            result = adapter(native).invoke("outcome_define", request("contract"))
            self.assertEqual(result["error"], "malformed_native_response")
            self.assertFalse(result["may_have_persisted"])
            self.assertNotIn("synthetic-sensitive-detail", json.dumps(result))
            self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_incomplete_empty_worker_pins_fail_closed_before_dispatch(self):
        for pin in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_DB"):
            native = Native()
            tools = adapter(native, {pin: ""})
            result = tools.invoke("outcome_show", {"board": BOARD, "task_id": TASK})
            self.assertEqual(result["error"], "board_fence")
            self.assertEqual(native.calls, [])

    def test_due_exact_bounds_earliest_manual_native_anchor_and_no_lifecycle_effect(self):
        golden = load("golden.json")
        contract = copy.deepcopy(golden["contract"])
        contract["timing"].update(anchor="done", delay_seconds=86400, deadline="2026-10-04T00:00:00Z")
        native = Native([source(contract)])
        native.state["task"]["completed_at"] = 1790812800  # 2026-10-01 UTC.
        before = copy.deepcopy(native.state)
        for current, expected in ((datetime(2026, 10, 1), "not_due"), (datetime(2026, 10, 2), "due"),
                                  (datetime(2026, 10, 3), "overdue")):
            tools = OutcomeAdapter(native, environment={}, clock=lambda: current)
            result = tools.invoke("outcome_check", {"board": BOARD, "task_id": TASK})
            self.assertEqual(result["view"]["due_status"], expected)
            self.assertEqual(result["view"]["due_at"], "2026-10-02T00:00:00Z")
            self.assertEqual(result["view"]["anchor_sources"], {"done": "native_completion"})
        self.assertEqual(native.state, before)
        contract["timing"].update(anchor=None, delay_seconds=None, deadline=None, observe_when="manual")
        native.state["comments"] = [source(contract)]
        result = adapter(native).invoke("outcome_check", {"board": BOARD, "task_id": TASK})
        self.assertEqual(result["view"]["due_status"], "due_time_unknown")

    def test_tool_input_schemas_are_closed_offline_and_match_handlers(self):
        for name in ("outcome_define", "outcome_observe", "outcome_show", "outcome_check"):
            schema = tool_schema(name)["parameters"]
            Draft202012Validator.check_schema(schema)
            self.assertNotIn('"$ref"', json.dumps(schema))
            params = request("contract" if name == "outcome_define" else "confirmed") if name in {"outcome_define", "outcome_observe"} else {"board": BOARD, "task_id": TASK}
            self.assertTrue(Draft202012Validator(schema).is_valid(params))
            self.assertFalse(Draft202012Validator(schema).is_valid(dict(params, unexpected="data")))
            field = "contract" if name == "outcome_define" else "observation"
            if field in params:
                bad = copy.deepcopy(params)
                bad[field]["payload_sha256"] = "0" * 64
                self.assertFalse(Draft202012Validator(schema).is_valid(bad))
        with self.assertRaises(records.NoSuchResource):
            records.offline("https://example.invalid/remote")

    def test_native_ast_calls_are_literal_allowlisted_and_no_reflection_or_execution(self):
        root = Path(__file__).resolve().parents[1] / "hermes_outcome_loop"
        names = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, {"eval", "exec", "open", "__import__", "getattr", "setattr"})
                    elif isinstance(node.func, ast.Attribute) and node.func.attr == "native":
                        self.assertIsInstance(node.args[0], ast.Constant)
                        names.append(node.args[0].value)
        self.assertEqual(set(names), {"kanban_show", "kanban_comment"})
        self.assertEqual(NATIVE_TOOLS, frozenset(names))
        native = Native()
        for tool in ("kanban_create", "kanban_link", "kanban_request_review", "kanban_complete", "kanban_block",
                     "kanban_heartbeat", "kanban_request_changes", "terminal", "read_file"):
            with self.assertRaisesRegex(ValueError, "native_tool_forbidden"):
                adapter(native).native(tool, {"board": BOARD, "task_id": TASK})
        self.assertEqual(native.calls, [])


if __name__ == "__main__":
    unittest.main()
