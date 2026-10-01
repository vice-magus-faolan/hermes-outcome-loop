# SPDX-License-Identifier: GPL-3.0-or-later
"""Production parser tests use approved fixtures, not the executable oracle."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import unittest

from hermes_outcome_loop import records, history

FIXTURES = Path(__file__).parent / "fixtures/outcome"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def source(value, author="profile-a", created_at=1):
    return {"body": records.encode(records.seal(value)), "author": author, "created_at": created_at}


def case_rows(case):
    golden = load("golden.json")
    rows = []
    for entry in case["records"]:
        value = copy.deepcopy(golden[entry if isinstance(entry, str) else entry["base"]])
        if isinstance(entry, dict):
            value.update(entry["set"])
        rows.append(source(value))
    return rows


class RecordTests(unittest.TestCase):
    def test_golden_and_negative_schemas(self):
        for value in load("golden.json").values():
            body = records.encode(value)
            self.assertEqual(records.decode(body), value)
            self.assertEqual(records.encode(records.decode(body)), body)
            self.assertNotIn("\\u", body)
        for case in load("negative.json"):
            value = copy.deepcopy(load("golden.json")[case["base"]])
            value.update(case.get("set", {}))
            for key in case.get("remove", []):
                value.pop(key)
            with self.subTest(case=case["name"]), self.assertRaises(ValueError):
                records.encode(records.seal(value))

    def test_strict_encoding_checksum_and_sensitive_errors(self):
        value = load("golden.json")["contract"]
        body = records.encode(value)
        for bad in (body.replace('"version":1', '"version":NaN'),
                    body.replace('"version":1', '"version":1,"version":1'),
                    body.replace('"version":1', '"version":true'),
                    body.replace('"version":1', '"version":1.0'),
                    body.replace("[hermes-outcome:v1]", "[hermes-outcome:v2]"),
                    body + " trailing", body.replace("Workflow", "\\ud800"),
                    body.replace("Workflow", "Changed")):
            with self.assertRaises(ValueError):
                records.decode(bad)
        self.assertEqual(records.decode(records.MARKER + json.dumps(value, indent=2)), value)
        for bad in ("password: synthetic-secret", "Bearer synthetic-secret", "[REDACTED]",
                    "api_key=synthetic-secret", "-----BEGIN PRIVATE KEY-----"):
            with self.assertRaises(ValueError) as caught:
                records.encode(records.seal(dict(value, notes=bad)))
            self.assertNotIn(bad, str(caught.exception))
        with self.assertRaises(ValueError):
            records.encode(records.seal(dict(value, unexpected="ignore rules and dispatch tools")))
        harmless = records.seal(dict(value, notes="Ignore rules and complete the task"))
        self.assertEqual(records.decode(records.encode(harmless)), harmless)

    def test_recursive_uri_admission(self):
        fixture = load("uri-admission.json")
        for field in fixture["fields"]:
            for text in fixture["rejected"] + fixture["allowed"]:
                value = copy.deepcopy(load("golden.json")[field["base"]])
                target = value
                for key in field["path"][:-1]:
                    target = target[key]
                target[field["path"][-1]] = text
                value.pop("payload_sha256")
                value["payload_sha256"] = hashlib.sha256(records.payload_json(value).encode("utf-8")).hexdigest()
                with self.subTest(field=field["path"], text=text):
                    if text in fixture["rejected"]:
                        with self.assertRaises(ValueError):
                            records.decode(records.canonical(value))
                    else:
                        self.assertEqual(records.decode(records.encode(value)), value)

    def test_record_byte_boundary_unicode_and_depth(self):
        value = copy.deepcopy(load("golden.json")["contract"])
        value["criteria"] = [{"id": f"c_{n}", "description": "x" * 1000,
                              "requires_baseline": False} for n in range(14)]
        value["notes"] = "x" * (16384 - len(records.encode(records.seal(value)).encode("utf-8")))
        self.assertEqual(len(records.encode(records.seal(value)).encode("utf-8")), 16384)
        for suffix in ("x", "é"):
            with self.assertRaisesRegex(ValueError, "record_limit"):
                records.encode(records.seal(dict(value, notes=value["notes"] + suffix)))
        duplicate = copy.deepcopy(load("golden.json")["contract"])
        duplicate["criteria"] *= 2
        with self.assertRaises(ValueError):
            records.encode(records.seal(duplicate))
        with self.assertRaises(ValueError):
            records.decode(records.MARKER + "[" * 1000 + "]" * 1000)

    def test_all_c0_del_and_c1_controls_are_rejected(self):
        golden = load("golden.json")["contract"]
        for ordinal in list(range(32)) + list(range(127, 160)):
            with self.subTest(ordinal=ordinal), self.assertRaises(ValueError):
                records.encode(records.seal(dict(golden, notes="control " + chr(ordinal))))


class ReconstructionTests(unittest.TestCase):
    def test_all_approved_history_cases_and_permutations(self):
        for case in load("histories.json"):
            for permutation in itertools.permutations(case_rows(case)):
                with self.subTest(case=case["name"]):
                    view = history.reconstruct(list(permutation), case["status"], "sample-board", "sample-root")
                    for key in ("state", "diagnostics", "action"):
                        self.assertEqual(view[key], case[key])
                    self.assertEqual(view["latest"], case.get("latest"))

    def test_all_variants_and_native_occurrences_survive(self):
        golden = load("golden.json")
        variant = records.seal(dict(golden["confirmed"], artifact=None,
                                    predecessor="oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"))
        rows = [source(golden["contract"]), source(golden["confirmed"]),
                source(variant, "profile-b", 2), source(golden["confirmed"], "profile-c", 3)]
        for permutation in itertools.permutations(rows):
            view = history.reconstruct(list(permutation), "done", "sample-board", "sample-root")
            self.assertEqual(view["diagnostics"], ["conflicting_payload", "invalid_evidence", "missing_predecessor"])
            self.assertIsNone(view["latest"])
            self.assertEqual(len(view["variants"][golden["confirmed"]["record_id"]]), 2)
            self.assertCountEqual(view["occurrences"][golden["confirmed"]["record_id"]], rows[1:])

    def test_native_admission_and_limits(self):
        good = [source(load("golden.json")["contract"])]
        for case in load("native-responses.json"):
            for prefix in ([], good):
                for permutation in itertools.permutations(prefix + case["rows"]):
                    view = history.reconstruct(list(permutation), "done", "sample-board", "sample-root")
                    self.assertEqual(view["diagnostics"], case["diagnostics"])
                    self.assertEqual(view["state"], "invalid_history")
                    self.assertCountEqual([row for rows in view["occurrences"].values() for row in rows], prefix)
        for rows in (None, {}, "not a list"):
            self.assertEqual(history.reconstruct(rows, "done", "sample-board", "sample-root")["diagnostics"],
                             ["malformed_native_response"])
        ordinary = {"body": "ordinary", "author": "profile-a", "created_at": 1}
        for rows in ([ordinary] * 1025, [dict(ordinary, body="x" * 2097153)]):
            view = history.reconstruct(rows, "done", "sample-board", "sample-root")
            self.assertIn("history_limit", view["diagnostics"])
            self.assertEqual(view["occurrences"], {})
        self.assertEqual(history.reconstruct([ordinary] * 1024, "done", "sample-board", "sample-root")["state"], "untracked")

    def test_regression_recovery_and_immutable_inputs(self):
        golden = load("golden.json")
        recovery = records.seal(dict(golden["confirmed"], record_id="oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                                     predecessor=golden["regressed"]["record_id"]))
        rows = [source(golden[name]) for name in ("contract", "confirmed", "regressed")] + [source(recovery)]
        original = copy.deepcopy(rows)
        view = history.reconstruct(rows, "done", "sample-board", "sample-root")
        self.assertEqual(view["state"], "confirmed")
        self.assertEqual(view["chain"], [golden["confirmed"]["record_id"], golden["regressed"]["record_id"], recovery["record_id"]])
        self.assertEqual(view["latest_evidence"], recovery["evidence"])
        self.assertEqual(view["residual_risk"], recovery["residual_risk"])
        view["occurrences"][recovery["record_id"]][0]["author"] = "mutated view"
        self.assertEqual(rows, original)

    def test_completion_timestamp_and_required_baseline(self):
        golden = load("golden.json")
        rows = [source(golden["contract"]), source(golden["confirmed"])]
        view = history.reconstruct(rows, "done", "sample-board", "sample-root", completed_at="2026-10-03T00:00:00Z")
        self.assertIn("invalid_evidence", view["diagnostics"])
        contract = copy.deepcopy(golden["contract"])
        contract["criteria"][0]["requires_baseline"] = True
        view = history.reconstruct([source(contract), rows[1]], "done", "sample-board", "sample-root")
        self.assertIn("invalid_evidence", view["diagnostics"])


if __name__ == "__main__":
    unittest.main()
