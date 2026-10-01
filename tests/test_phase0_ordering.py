# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded causal feasibility checks; field names are not production schemas."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase0_ordering", ROOT / "scripts/phase0_ordering.py")
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load causal feasibility module")
ordering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ordering)


def occurrence(identifier, predecessor=None, summary="evidence", author="profile-a", time=1):
    payload = {"record_id": identifier, "contract_id": "probe-contract",
               "predecessor": predecessor, "summary": summary}
    return {"body": ordering.MARKER + json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "author": author, "created_at": time}


class CausalFeasibilityTests(unittest.TestCase):
    def test_reverse_input_tied_timestamps_never_select_id_order(self):
        rows = [occurrence("z"), occurrence("a", "z"), occurrence("m", "a")]
        for sequence in (rows, rows[::-1], [rows[1], rows[2], rows[0]]):
            result = ordering.reconstruct(sequence)
            self.assertEqual(result["latest"], "m")
            self.assertEqual(result["diagnostics"], [])

    def test_identical_retries_retain_each_native_occurrence(self):
        rows = [occurrence("z"), occurrence("z", author="profile-b", time=2)]
        result = ordering.reconstruct(rows)
        self.assertEqual(result["latest"], "z")
        self.assertEqual(result["occurrences"]["z"], rows)

    def test_conflict_fork_missing_and_cycle_have_no_winner(self):
        cases = {
            "conflict": [occurrence("z"), occurrence("z", summary="changed")],
            "fork": [occurrence("z"), occurrence("a", "z"), occurrence("m", "z")],
            "missing_predecessor": [occurrence("a", "absent")],
            "cycle": [occurrence("a", "m"), occurrence("m", "a")],
            "multiple_roots": [occurrence("z"), occurrence("a")],
        }
        for diagnostic, rows in cases.items():
            for sequence in (rows, rows[::-1]):
                with self.subTest(diagnostic=diagnostic):
                    result = ordering.reconstruct(sequence)
                    self.assertIn(diagnostic, result["diagnostics"])
                    self.assertIsNone(result["latest"])
                    self.assertEqual(sum(map(len, result["occurrences"].values())), len(rows))

    def test_unreadable_and_bounded_history_fail_closed(self):
        for rows in ([{"body": ordering.MARKER + "{", "author": "a", "created_at": 1}],
                     [occurrence("z")] * (ordering.MAX_RECORDS + 1),
                     [occurrence("z", summary="x" * ordering.MAX_BYTES)]):
            result = ordering.reconstruct(rows)
            self.assertIsNone(result["latest"])
            self.assertTrue(result["diagnostics"])

    def test_cycle_with_tail_and_disjoint_valid_chain_not_hidden(self):
        result = ordering.reconstruct([occurrence("a", "b"), occurrence("b", "a"),
                                       occurrence("c", "b"), occurrence("z")])
        self.assertIn("cycle", result["diagnostics"])
        self.assertIsNone(result["latest"])

    def test_history_total_bytes_are_bounded_not_just_record_count(self):
        rows = [occurrence("z", summary="x" * (ordering.MAX_BYTES - 256))] * 130
        self.assertLess(len(rows), ordering.MAX_RECORDS)
        result = ordering.reconstruct(rows)
        self.assertEqual(result["diagnostics"], ["history_byte_limit"])
        self.assertIsNone(result["latest"])
