# SPDX-License-Identifier: GPL-3.0-or-later
"""Historical temporal admission and races; synthetic transport, not native proof."""
import copy
import unittest

from test_outcome_adapter import Native, adapter, request, BOARD, TASK
from test_outcome_core import load, source

# UTC midnight on October 1, 2 and 4, 2026, respectively.
FIRST, OBSERVED, CURRENT = 1790812800, 1790899200, 1791072000


def completion(identifier, ended, status="completed"):
    return {"id": identifier, "status": status, "outcome": "completed",
            "started_at": ended, "ended_at": ended}


def historical_native():
    golden = load("golden.json")
    rows = [source(golden["contract"]), source(golden["confirmed"])]
    rows[-1]["created_at"] = OBSERVED
    native = Native(rows)
    native.state["task"].update(completed_at=CURRENT, current_run_id=None)
    native.state["runs"] = [completion(1, FIRST), completion(2, CURRENT, "done")]
    return native


class RecompletionTests(unittest.TestCase):
    def show(self, native):
        return adapter(native).invoke("outcome_show", {"board": BOARD, "task_id": TASK})["view"]

    def test_historical_floor_is_independent_of_row_order(self):
        native = historical_native()
        expected = self.show(native)
        self.assertEqual(expected["state"], "confirmed")
        self.assertEqual(expected["observations"][0]["provenance"]["samples"][0]["created_at"], OBSERVED)
        native.state["comments"].reverse()
        native.state["runs"].reverse()
        self.assertEqual(self.show(native), expected)

    def test_missing_partial_malformed_or_ambiguous_runs_do_not_grandfather_comments(self):
        native = historical_native()
        runs = native.state["runs"]
        missing_start = copy.deepcopy(runs)
        missing_start[0].pop("started_at")
        bad_cases = [None, {}, [], runs[1:], missing_start, [*runs, runs[0]], [*runs, None]]
        for changes in ({"ended_at": None}, {"ended_at": True}, {"started_at": OBSERVED},
                        {"status": "blocked"}, {"status": []}, {"outcome": {}}, {"id": True}):
            bad_cases.append([dict(runs[0], **changes), runs[1]])
        for bad in bad_cases:
            with self.subTest(runs=bad):
                native = historical_native()
                native.state["runs"] = bad
                view = self.show(native)
                self.assertEqual(view["state"], "invalid_history")
                self.assertIn("completion_history_unavailable", view["diagnostics"])
                self.assertIsNone(view["latest"])
                result = adapter(native).invoke("outcome_observe", request("confirmed"))
                self.assertEqual(result["error"], "invalid_history")
                self.assertNotIn("kanban_comment", [name for name, _ in native.calls])
        native = historical_native()
        del native.state["runs"]
        self.assertIn("completion_history_unavailable", self.show(native)["diagnostics"])

    def test_each_occurrence_uses_latest_proven_delivery_not_earliest_or_logical_id(self):
        for mode in ("before_first", "intermediate_delivery", "new_backdated_occurrence"):
            with self.subTest(mode=mode):
                native = historical_native()
                if mode == "before_first":
                    native.state["runs"][0] = completion(1, OBSERVED + 1)
                    native.state["comments"][-1]["created_at"] = OBSERVED + 2
                elif mode == "intermediate_delivery":
                    native.state["runs"].append(completion(3, OBSERVED + 1))
                    native.state["comments"][-1]["created_at"] = OBSERVED + 2
                else:
                    duplicate = dict(native.state["comments"][-1], created_at=CURRENT)
                    native.state["comments"].append(duplicate)
                view = self.show(native)
                self.assertEqual(view["state"], "invalid_history")
                self.assertIn("invalid_evidence", view["diagnostics"])
                self.assertIsNone(view["latest"])

    def test_missing_native_occurrence_provenance_still_blocks_historical_retry(self):
        native = historical_native()
        del native.state["comments"][-1]["author"]
        view = self.show(native)
        self.assertEqual(view["state"], "invalid_history")
        self.assertIn("missing_provenance", view["diagnostics"])
        result = adapter(native).invoke("outcome_observe", request("confirmed"))
        self.assertEqual(result["error"], "invalid_history")
        self.assertNotIn("kanban_comment", [name for name, _ in native.calls])

    def test_postwrite_recompletion_is_uncertain_even_if_historical_view_remains_valid(self):
        for same_second in (False, True):
            with self.subTest(same_second=same_second):
                native = Native([source(load("golden.json")["contract"])])
                initial = OBSERVED if same_second else FIRST
                native.state["task"].update(completed_at=initial, current_run_id=None)
                native.state["runs"] = [completion(1, initial)]
                before_task = copy.deepcopy(native.state["task"])

                def recomplete(native):
                    native.state["comments"][-1]["created_at"] = OBSERVED
                    anchor = OBSERVED if same_second else CURRENT
                    native.state["task"].update(completed_at=anchor, current_run_id=None)
                    native.state["runs"].append(completion(2, anchor, "done"))

                native.after = recomplete
                result = adapter(native).invoke("outcome_observe", request("confirmed"))
                self.assertIsNone(native.state["task"]["current_run_id"])
                self.assertEqual(len(native.state["runs"]), 2)
                if same_second:
                    self.assertEqual(native.state["task"], before_task)
                self.assertEqual(result["error"], "write_unverified")
                self.assertTrue(result["may_have_persisted"])
                self.assertEqual(result["diagnostics"], ["lifecycle_changed"])
                self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), 1)
                self.assertEqual(self.show(native)["state"], "confirmed")

    def test_missing_or_malformed_run_identity_fails_closed_before_and_after_append(self):
        for bad in (None, {}, [], [{"id": 1}], [completion(1, FIRST), completion(1, FIRST)]):
            for postwrite in (False, True):
                with self.subTest(runs=bad, postwrite=postwrite):
                    native = Native([source(load("golden.json")["contract"])])
                    native.state["task"].update(completed_at=FIRST, current_run_id=None)
                    native.state["runs"] = [completion(1, FIRST)]

                    def corrupt(native):
                        native.state["runs"] = bad

                    if postwrite:
                        native.after = corrupt
                    else:
                        corrupt(native)
                    result = adapter(native).invoke("outcome_observe", request("confirmed"))
                    expected = "write_unverified" if postwrite else "completion_history_unavailable"
                    self.assertEqual(result["error"], expected)
                    self.assertEqual(result["diagnostics"], ["completion_history_unavailable"])
                    self.assertEqual(result["may_have_persisted"], postwrite)
                    self.assertEqual([name for name, _ in native.calls].count("kanban_comment"), int(postwrite))

    def test_unchanged_completed_runs_reordered_after_append_are_verified(self):
        native = historical_native()

        def reorder(native):
            native.state["comments"][-1]["created_at"] = CURRENT
            native.state["runs"].reverse()

        native.after = reorder
        result = adapter(native).invoke("outcome_observe", request("regressed", observed_at="2026-10-04T00:00:00Z"))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["acknowledgment"], "verified")


if __name__ == "__main__":
    unittest.main()
