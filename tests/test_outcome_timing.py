# SPDX-License-Identifier: GPL-3.0-or-later
"""Calendar-range timing regressions against the explicit fake native transport."""
import copy
from datetime import datetime
import unittest

from hermes_outcome_loop.adapter import OutcomeAdapter
from test_outcome_adapter import BOARD, TASK, Native, adapter, request
from test_outcome_core import load, source

MAX_UTC = "9999-12-31T23:59:59Z"
MAX_COMPLETION = 253402300799
MAX_DELAY = 31536000
TARGET = {"board": BOARD, "task_id": TASK}


class TimingTests(unittest.TestCase):
    def test_earlier_deadline_survives_overflowing_external_anchor(self):
        contract = copy.deepcopy(load("golden.json")["contract"])
        contract["timing"]["deadline"] = "2026-10-01T00:00:00Z"
        for anchor, diagnostics in ((MAX_UTC, ["derived_due_out_of_range"]),
                                    ("2026-10-04T00:00:00Z", [])):
            with self.subTest(anchor=anchor):
                native = Native([source(contract)])
                before = copy.deepcopy(native.state)
                result = adapter(native).invoke("outcome_check", dict(TARGET, anchors={"deployment": anchor}))
                self.assertTrue(result["ok"], result)
                view = result["view"]
                self.assertEqual(view["state"], "awaiting_observation")
                self.assertEqual(view["due_at"], "2026-10-01T00:00:00Z")
                self.assertEqual(view["due_status"], "overdue")
                self.assertEqual(view["timing_diagnostics"], diagnostics)
                self.assertEqual(view["diagnostics"], [])
                self.assertEqual(view["anchor_sources"], {"deployment": "caller_supplied"})
                self.assertEqual(native.state, before)
                self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_overflowing_done_bound_define_readback_retry_and_fresh_reads(self):
        native = Native()
        native.state["task"]["completed_at"] = MAX_COMPLETION
        params = request("contract")
        params["contract"]["timing"].update(anchor="done", delay_seconds=86400, deadline=None)
        defined = adapter(native).invoke("outcome_define", params)
        self.assertTrue(defined["ok"], defined)
        self.assertEqual(defined["acknowledgment"], "verified")
        self.assertEqual([name for name, _ in native.calls], ["kanban_show", "kanban_comment", "kanban_show"])
        before = copy.deepcopy(native.state)
        for name, arguments in (("outcome_define", params), ("outcome_show", TARGET), ("outcome_check", TARGET)):
            with self.subTest(tool=name):
                native.calls.clear()
                result = adapter(native).invoke(name, arguments)
                self.assertTrue(result["ok"], result)
                if name == "outcome_define":
                    self.assertEqual(result["acknowledgment"], "identical_retry")
                view = result["view"]
                self.assertEqual(view["state"], "awaiting_observation")
                self.assertEqual(view["action"], "OBSERVATION_REQUIRED")
                self.assertEqual(view["diagnostics"], [])
                self.assertEqual(view["timing_diagnostics"], ["derived_due_out_of_range"])
                self.assertEqual(view["due_status"], "not_due")
                self.assertIsNone(view["due_at"])
                self.assertIn("outside supported UTC range", view["timing_message"])
                self.assertEqual(view["anchor_sources"], {"done": "native_completion"})
                self.assertEqual(native.state, before)
                self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_out_of_range_timing_does_not_block_observation_or_invent_cadence(self):
        contract = copy.deepcopy(load("golden.json")["contract"])
        contract["timing"].update(anchor="done", delay_seconds=MAX_DELAY)
        native = Native([source(contract)])
        native.state["task"]["completed_at"] = MAX_COMPLETION
        observed = adapter(native).invoke("outcome_observe", request("confirmed", observed_at=MAX_UTC))
        self.assertTrue(observed["ok"], observed)
        self.assertEqual(observed["acknowledgment"], "verified")
        self.assertEqual(observed["view"]["state"], "confirmed")
        self.assertEqual(observed["view"]["action"], "NO_ACTION_REQUIRED")
        self.assertEqual(observed["view"]["due_status"], "not_applicable")
        self.assertEqual(observed["view"]["timing_diagnostics"], [])
        self.assertEqual(observed["view"]["diagnostics"], [])
        self.assertEqual([name for name, _ in native.calls], ["kanban_show", "kanban_comment", "kanban_show"])
        native.calls.clear()
        fresh = adapter(native).invoke("outcome_check", TARGET)
        self.assertEqual(fresh["view"], observed["view"])
        self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_upper_range_zero_max_delay_and_last_representable_second(self):
        cases = [(MAX_UTC, 0, MAX_UTC, "due", []),
                 ("9999-12-30T23:59:59Z", 86400, MAX_UTC, "due", []),
                 (MAX_UTC, 1, None, "not_due", ["derived_due_out_of_range"]),
                 (MAX_UTC, MAX_DELAY, None, "not_due", ["derived_due_out_of_range"])]
        for anchor in ("done", "integration", "deployment", "first_workflow"):
            for start, delay, due_at, status, diagnostics in cases:
                with self.subTest(anchor=anchor, start=start, delay=delay):
                    contract = copy.deepcopy(load("golden.json")["contract"])
                    contract["timing"].update(anchor=anchor, delay_seconds=delay, deadline=None)
                    native = Native([source(contract)])
                    params: dict[str, object] = dict(TARGET)
                    if anchor == "done":
                        native.state["task"]["completed_at"] = MAX_COMPLETION if start == MAX_UTC else MAX_COMPLETION - 86400
                    else:
                        params["anchors"] = {anchor: start}
                    tools = OutcomeAdapter(native, environment={}, clock=lambda: datetime(9999, 12, 31, 23, 59, 59))
                    result = tools.invoke("outcome_check", params)
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(result["view"]["due_at"], due_at)
                    self.assertEqual(result["view"]["due_status"], status)
                    self.assertEqual(result["view"]["timing_diagnostics"], diagnostics)
                    self.assertEqual(result["view"]["diagnostics"], [])
                    self.assertEqual([name for name, _ in native.calls], ["kanban_show"])

    def test_overflow_with_last_second_deadline_uses_known_bound(self):
        contract = copy.deepcopy(load("golden.json")["contract"])
        contract["timing"].update(deadline=MAX_UTC, delay_seconds=MAX_DELAY)
        native = Native([source(contract)])
        for current, status in ((datetime(9999, 12, 31), "not_due"),
                                (datetime(9999, 12, 31, 23, 59, 59), "due")):
            tools = OutcomeAdapter(native, environment={}, clock=lambda: current)
            result = tools.invoke("outcome_check", dict(TARGET, anchors={"deployment": MAX_UTC}))
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["view"]["due_at"], MAX_UTC)
            self.assertEqual(result["view"]["due_status"], status)
            self.assertEqual(result["view"]["timing_diagnostics"], ["derived_due_out_of_range"])

    def test_full_timestamp_range_serialization_and_unknown_are_distinct(self):
        for start in ("0001-01-01T00:00:00Z", "0009-01-01T00:00:00Z", "0999-01-01T00:00:00Z", MAX_UTC):
            with self.subTest(start=start):
                contract = copy.deepcopy(load("golden.json")["contract"])
                contract["timing"].update(delay_seconds=0)
                native = Native([source(contract)])
                result = adapter(native).invoke("outcome_check", dict(TARGET, anchors={"deployment": start}))
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["view"]["due_at"], start)
                self.assertEqual(result["view"]["timing_diagnostics"], [])
                unknown = adapter(native).invoke("outcome_check", TARGET)
                self.assertEqual(unknown["view"]["due_status"], "due_time_unknown")
                self.assertEqual(unknown["view"]["timing_diagnostics"], [])
                self.assertIsNone(unknown["view"]["due_at"])
                native.state["task"]["status"] = "running"
                planned = adapter(native).invoke("outcome_check", dict(TARGET, anchors={"deployment": MAX_UTC}))
                self.assertEqual(planned["view"]["due_status"], "not_applicable")
                self.assertEqual(planned["view"]["timing_diagnostics"], [])


if __name__ == "__main__":
    unittest.main()
