# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise encoded public replies, not source shape or internal-only projections."""
import copy
import json
import os
import unittest
from unittest.mock import patch

from hermes_outcome_loop import register, history, records
from test_outcome_adapter import Native, request, BOARD, TASK
from test_outcome_core import load, source


class PublicResultTests(unittest.TestCase):
    def handlers(self, native):
        with patch.dict(os.environ, {}, clear=True):
            register(native)
        return native.tools

    def call(self, tools, name, params):
        with patch.dict(os.environ, {}, clear=True):
            raw = tools[name]["handler"](params)
        self.assertLessEqual(len(raw.encode("utf-8")), 32768)
        result = json.loads(raw)
        self.assertNotIn("occurrences", result.get("view", {}))
        self.assertNotIn("variants", result.get("view", {}))
        return result

    def large_history(self, count=96):
        golden = load("golden.json")
        rows, previous = [source(golden["contract"])], None
        for index in range(count):
            value = copy.deepcopy(golden["confirmed"])
            value.update(record_id=f"oo_{index:032x}", predecessor=previous,
                         summary="界" * 1024)
            value["evidence"][0]["summary"] = "界" * 1024
            rows.append(source(value, "observer", index))
            previous = value["record_id"]
        return rows, previous

    def test_large_causal_history_all_four_handlers_and_old_retries(self):
        rows, previous = self.large_history()
        native = Native(rows)
        tools = self.handlers(native)
        original = copy.deepcopy(native.state)
        for name in ("outcome_show", "outcome_check"):
            result = self.call(tools, name, {"board": BOARD, "task_id": TASK})
            view = result["view"]
            self.assertEqual(view["state"], "confirmed")
            self.assertEqual(view["latest"], previous)
            self.assertEqual(view["observations"][-1]["record_id"], previous)
            self.assertEqual(view["observation_count"], 96)
            self.assertEqual(view["omitted"]["observations"], 96 - len(view["observations"]))
            self.assertGreater(view["omitted"]["chain"], 0)
        self.assertEqual(native.state, original)
        definition = self.call(tools, "outcome_define", request("contract"))
        self.assertEqual(definition["acknowledgment"], "identical_retry")
        new = request("confirmed", record_id="oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", predecessor=previous)
        result = self.call(tools, "outcome_observe", new)
        self.assertEqual(result["acknowledgment"], "verified")
        self.assertEqual(result["view"]["observations"][-1]["predecessor"], previous)
        self.assertEqual(native.state["comments"][:-1], original["comments"])
        self.assertEqual(records.decode(native.state["comments"][-1]["body"]), records.seal(new["observation"]))
        retry = self.call(tools, "outcome_observe", new)
        self.assertEqual(retry["acknowledgment"], "identical_retry")
        old = records.decode(rows[1]["body"])
        old.pop("payload_sha256")
        retry = self.call(tools, "outcome_observe", {"board": BOARD, "task_id": TASK, "observation": old})
        self.assertEqual(retry["record_id"], old["record_id"])
        self.assertEqual(retry["view"]["latest"], new["observation"]["record_id"])
        self.assertEqual(len(native.state["comments"]), 98)

    def test_conflicting_variants_are_summarized_without_choosing_a_winner(self):
        rows = [source(load("golden.json")["contract"])]
        for index in range(80):
            value = copy.deepcopy(load("golden.json")["confirmed"])
            value.update(record_id=f"oo_{index // 10:032x}", summary="界" * 1000 + str(index))
            rows.append(source(value, "observer-" + str(index), index))
        native = Native(rows)
        original = copy.deepcopy(native.state)
        tools = self.handlers(native)
        for name in ("outcome_show", "outcome_check"):
            result = self.call(tools, name, {"board": BOARD, "task_id": TASK})
            view = result["view"]
            self.assertEqual(view["state"], "invalid_history")
            self.assertIn("conflicting_payload", view["diagnostics"])
            self.assertIn("fork", view["diagnostics"])
            self.assertIsNone(view["latest"])
            self.assertEqual(view["observations"], [])
            self.assertEqual(view["observation_count"], 8)
            self.assertEqual(view["omitted"]["observations"], 8)
            self.assertGreater(len(view["conflicts"]), 0)
            for conflict in view["conflicts"]:
                self.assertEqual(conflict["variant_count"], 10)
                self.assertEqual(len(conflict["payload_sha256s"]), 8)
                self.assertEqual(conflict["omitted_payload_sha256s"], 2)
                self.assertNotIn("summary", conflict)
        rejected = self.call(tools, "outcome_define", request("contract"))
        self.assertEqual(rejected["error"], "invalid_history")
        self.assertEqual(native.state, original)
        internal = history.reconstruct(rows, "done", BOARD, TASK)
        self.assertEqual(sum(len(values) for values in internal["variants"].values()), 81)
        self.assertEqual(sum(len(values) for values in internal["occurrences"].values()), 81)

    def test_escaped_payloads_and_unbounded_native_provenance_fit_without_storage_loss(self):
        native = Native([{"body": "ordinary", "author": "x", "created_at": 1}] * 1000)
        tools = self.handlers(native)
        params = request("contract", objective='"' * 1024, expected_outcome='\\' * 2048)
        result = self.call(tools, "outcome_define", params)
        self.assertEqual(result["acknowledgment"], "verified")
        self.assertEqual(len(native.state["comments"]), 1001)
        native.state["comments"][-1]["author"] = "界" * 100000
        before = copy.deepcopy(native.state)
        result = self.call(tools, "outcome_show", {"board": BOARD, "task_id": TASK})
        self.assertEqual(result["view"]["contract"]["provenance"]["omitted_occurrences"], 1)
        self.assertEqual(native.state, before)
        self.assertEqual(records.decode(native.state["comments"][-1]["body"]), records.seal(params["contract"]))

    def test_compact_overflow_keeps_head_identity_and_explicit_field_omissions(self):
        golden = load("golden.json")
        contract = copy.deepcopy(golden["contract"])
        contract.update(objective="x" * 1024, expected_outcome="x" * 2048, notes="x" * 2048)
        contract["criteria"] = [{"id": f"c_item{index}", "description": "x" * 500,
                                 "requires_baseline": False} for index in range(16)]
        observation = copy.deepcopy(golden["confirmed"])
        observation.update(summary="x" * 1024, environment="x" * 512, artifact="x" * 512)
        observation["evidence"] = [{**golden["confirmed"]["evidence"][0],
                                    "criterion_id": criterion["id"], "summary": "x" * 650}
                                   for criterion in contract["criteria"]]
        rows = [source(value, "a" * 450, index)
                for value in (contract, observation) for index in range(4)]
        native = Native(rows)
        before = copy.deepcopy(native.state)
        result = self.call(self.handlers(native), "outcome_show", {"board": BOARD, "task_id": TASK})
        view = result["view"]
        self.assertEqual(view["state"], "confirmed")
        self.assertEqual(view["latest"], observation["record_id"])
        self.assertEqual(view["observations"][-1]["predecessor"], None)
        self.assertTrue(any(record["omitted_fields"] for record in [view["contract"], *view["observations"]]))
        self.assertEqual(view["occurrence_count"], 8)
        self.assertEqual(native.state, before)
