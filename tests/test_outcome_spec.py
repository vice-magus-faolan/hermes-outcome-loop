# SPDX-License-Identifier: GPL-3.0-or-later
"""Executable ADR acceptance cases, not production-plugin integration proof."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/outcome"
spec = importlib.util.spec_from_file_location("outcome_spec", ROOT / "scripts/outcome_spec.py")
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load executable record specification")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def replace_path(record, path, value):
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


class SchemaTests(unittest.TestCase):
    def test_metaschemas_and_closed_offline_registry(self):
        oracle.check_schemas()
        with self.assertRaises(ValueError):
            oracle.check_refs({"$ref": "https://example.invalid/remote"}, set())
        with self.assertRaises(oracle.NoSuchResource):
            oracle.no_remote("https://example.invalid/remote")

    def test_golden_canonical_utf8_roundtrips(self):
        for record in load("golden.json").values():
            with self.subTest(record=record["record_id"]):
                body = oracle.encode(record)
                self.assertEqual(oracle.decode(body), record)
                self.assertEqual(oracle.encode(oracle.decode(body)), body)
                self.assertNotIn("\\u", body)

    def test_negative_shapes_are_rejected(self):
        golden = load("golden.json")
        for case in load("negative.json"):
            value = copy.deepcopy(golden[case["base"]])
            value.update(case.get("set", {}))
            for key in case.get("remove", []):
                value.pop(key)
            with self.subTest(case=case["name"]), self.assertRaises(ValueError):
                oracle.encode(oracle.seal(value))

    def test_strict_json_marker_keys_numbers_and_unicode(self):
        body = oracle.encode(load("golden.json")["contract"])
        invalid = [body.replace('"version":1', '"version":NaN'),
                   body.replace('"version":1', '"version":1,"version":1'),
                   body.replace('"version":1', '"version":2'),
                   body.replace("[hermes-outcome:v1]", "[hermes-outcome:v2]"),
                   body + " trailing", body.replace("Workflow", "\\ud800")]
        for candidate in invalid:
            with self.subTest(candidate=candidate[:60]), self.assertRaises(ValueError):
                oracle.decode(candidate)

    def test_exact_byte_limit_rejects_not_truncates(self):
        # A long criterion list reaches the byte cap without violating field caps.
        record = copy.deepcopy(load("golden.json")["contract"])
        record["criteria"] = [{"id": f"c_{n}", "description": "x" * 1000,
                               "requires_baseline": False} for n in range(14)]
        body = oracle.encode(oracle.seal(record))
        remaining = oracle.POLICY["max_record_bytes"] - len(body.encode("utf-8"))
        record["notes"] = "x" * remaining
        self.assertEqual(len(oracle.encode(oracle.seal(record)).encode("utf-8")), 16384)
        for suffix in ("x", "é"):
            oversized = dict(record, notes=record["notes"] + suffix)
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "record_limit"):
                oracle.encode(oracle.seal(oversized))


    def test_field_caps_and_unique_criterion_ids(self):
        golden = load("golden.json")
        for field, limit in [("objective", 1024), ("expected_outcome", 2048), ("notes", 2048)]:
            value = dict(golden["contract"], **{field: "x" * (limit + 1)})
            with self.subTest(field=field), self.assertRaises(ValueError):
                oracle.encode(oracle.seal(value))
        contract = copy.deepcopy(golden["contract"])
        contract["criteria"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate_criterion"):
            oracle.encode(oracle.seal(contract))
        value = dict(golden["confirmed"], residual_risk=[f"risk {n}" for n in range(9)])
        with self.assertRaises(ValueError):
            oracle.encode(oracle.seal(value))

    def test_checksum_survives_whitespace_not_changed_meaning(self):
        value = load("golden.json")["confirmed"]
        alternate = oracle.MARKER + json.dumps(value, ensure_ascii=False, indent=2)
        self.assertEqual(oracle.decode(alternate), value)
        changed = oracle.encode(value).replace("Workflow observed", "Changed assertion")
        with self.assertRaisesRegex(ValueError, "integrity_mismatch"):
            oracle.decode(changed)
        rows = [oracle.occurrence(load("golden.json")["contract"]),
                {"body": changed, "author": "profile-a", "created_at": 1}]
        result = oracle.reconstruct(rows, "done", "sample-board", "sample-root")
        self.assertEqual(result["state"], "invalid_history")
        self.assertIn("integrity_mismatch", result["diagnostics"])


class HistoryTests(unittest.TestCase):
    def test_golden_states_all_five_results_and_regression(self):
        for case in load("histories.json"):
            with self.subTest(case=case["name"]):
                result = oracle.evaluate_case(case, load("golden.json"))
                self.assertEqual(result["state"], case["state"])
                self.assertEqual(result["diagnostics"], case["diagnostics"])
                self.assertEqual(result["latest"], case.get("latest"))
                self.assertEqual(result["action"], case["action"])

    def test_permutations_tied_times_and_retry_provenance(self):
        golden = load("golden.json")
        rows = [oracle.occurrence(golden[name]) for name in ("contract", "confirmed", "regressed")]
        for permutation in itertools.permutations(rows):
            result = oracle.reconstruct(list(permutation), "done", "sample-board", "sample-root")
            self.assertEqual(result["latest"], golden["regressed"]["record_id"])
            self.assertEqual(result["state"], "regressed")
        rows.append(oracle.occurrence(golden["confirmed"], "profile-b", 2))
        result = oracle.reconstruct(rows, "done", "sample-board", "sample-root")
        occurrences = result["occurrences"][golden["confirmed"]["record_id"]]
        self.assertEqual(len(occurrences), 2)
        self.assertEqual({row["author"] for row in occurrences}, {"profile-a", "profile-b"})

    def test_invalid_history_permutations_never_resolve_conflicts(self):
        golden = load("golden.json")
        for case in load("histories.json"):
            if case["state"] != "invalid_history":
                continue
            for permutation in itertools.permutations(case["records"]):
                shuffled = dict(case, records=list(permutation))
                with self.subTest(case=case["name"]):
                    result = oracle.evaluate_case(shuffled, golden)
                    self.assertEqual(result["diagnostics"], case["diagnostics"])
                    self.assertIsNone(result["latest"])

    def test_conflicting_variants_retain_every_native_occurrence(self):
        golden = load("golden.json")
        variant = oracle.seal(dict(golden["confirmed"], artifact=None))
        rows = [oracle.occurrence(golden["contract"]),
                oracle.occurrence(golden["confirmed"], "profile-a", 1),
                oracle.occurrence(variant, "profile-b", 2),
                oracle.occurrence(golden["confirmed"], "profile-c", 3)]
        for permutation in itertools.permutations(rows):
            result = oracle.reconstruct(list(permutation), "done", "sample-board", "sample-root")
            self.assertEqual(result["diagnostics"], ["conflicting_payload", "invalid_evidence"])
            self.assertIsNone(result["latest"])
            sources = result["occurrences"][golden["confirmed"]["record_id"]]
            self.assertCountEqual(sources, rows[1:])

    def test_malformed_native_response_fixtures_fail_observationally(self):
        golden = load("golden.json")
        valid = [oracle.occurrence(golden["contract"]), oracle.occurrence(golden["confirmed"])]
        for case in load("native-responses.json"):
            for prefix in ([], valid):
                rows = prefix + case["rows"]
                for permutation in itertools.permutations(rows):
                    with self.subTest(case=case["name"], mixed=bool(prefix)):
                        result = oracle.reconstruct(list(permutation), "done", "sample-board", "sample-root")
                        self.assertEqual(result["state"], "invalid_history")
                        self.assertEqual(result["diagnostics"], case["diagnostics"])
                        self.assertIsNone(result["latest"])
                        self.assertEqual(result["action"], "HISTORY_ATTENTION")
                        retained = [row for sources in result["occurrences"].values() for row in sources]
                        self.assertCountEqual(retained, prefix)
                        with self.assertRaisesRegex(ValueError, "invalid_history"):
                            oracle.preflight(golden["contract"], list(permutation), "done")
        for container in (None, {}, "synthetic-invalid-list"):
            result = oracle.reconstruct(container, "done", "sample-board", "sample-root")
            self.assertEqual(result["state"], "invalid_history")
            self.assertEqual(result["diagnostics"], ["malformed_native_response"])
        for field, value in (("author", None), ("created_at", True), ("created_at", -1)):
            row = dict(valid[1], **{field: value})
            result = oracle.reconstruct([valid[0], row], "done", "sample-board", "sample-root")
            self.assertEqual(result["diagnostics"], ["missing_provenance"])
            self.assertEqual(result["state"], "invalid_history")

    def test_recovery_is_new_head_and_preserves_regression(self):
        golden = load("golden.json")
        recovery = oracle.seal(dict(golden["confirmed"], record_id="oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                                   predecessor=golden["regressed"]["record_id"]))
        rows = [oracle.occurrence(golden[name]) for name in ("contract", "confirmed", "regressed")]
        rows.append(oracle.occurrence(recovery))
        result = oracle.reconstruct(rows, "done", "sample-board", "sample-root")
        self.assertEqual(result["state"], "confirmed")
        self.assertEqual(result["latest"], recovery["record_id"])
        self.assertIn(golden["regressed"]["record_id"], result["occurrences"])
        self.assertFalse(oracle.regression_criteria_valid(golden["inconclusive"], golden["regressed"]))

    def test_empty_is_untracked_but_marked_corruption_is_invalid(self):
        for body, expected in [("ordinary comment", "untracked"),
                               ("[hermes-outcome:v1]\n{", "invalid_history"),
                               ("[hermes-outcome:v9]\n{}", "invalid_history")]:
            result = oracle.reconstruct([{"body": body, "author": "profile-a", "created_at": 1}],
                                        "done", "sample-board", "sample-root")
            self.assertEqual(result["state"], expected)
            if expected == "invalid_history":
                golden = load("golden.json")
                rows = [oracle.occurrence(golden["contract"]), oracle.occurrence(golden["confirmed"]),
                        {"body": body, "author": "profile-a", "created_at": 1}]
                mixed = oracle.reconstruct(rows, "done", "sample-board", "sample-root")
                self.assertEqual(mixed["state"], "invalid_history")
                self.assertIsNone(mixed["latest"])

    def test_history_limits_include_unrelated_comments_and_retries(self):
        row = {"body": "ordinary", "author": "profile-a", "created_at": 1}
        for rows in ([row] * 1025, [dict(row, body="x" * 2100000)]):
            result = oracle.reconstruct(rows, "done", "sample-board", "sample-root")
            self.assertEqual(result["state"], "invalid_history")
            self.assertIn("history_limit", result["diagnostics"])
        result = oracle.reconstruct([dict(row, body="x" * 2100000, author=None)],
                                    "done", "sample-board", "sample-root")
        self.assertEqual(result["diagnostics"], ["history_limit", "missing_provenance"])

    def test_missing_native_provenance_is_not_caller_attribution(self):
        row = oracle.occurrence(load("golden.json")["contract"])
        del row["author"]
        result = oracle.reconstruct([row], "done", "sample-board", "sample-root")
        self.assertIn("missing_provenance", result["diagnostics"])
        self.assertEqual(result["state"], "invalid_history")


class AdmissionTests(unittest.TestCase):
    def test_uri_forms_in_every_nested_text_field(self):
        fixture = load("uri-admission.json")
        golden = load("golden.json")
        for entry in fixture["fields"]:
            for text in fixture["rejected"]:
                value = copy.deepcopy(golden[entry["base"]])
                replace_path(value, entry["path"], text)
                value = oracle.seal(value)
                with self.subTest(path=entry["path"], text=text):
                    with self.assertRaisesRegex(ValueError, "unsafe_pointer"):
                        oracle.encode(value)
                    with self.assertRaisesRegex(ValueError, "unsafe_pointer"):
                        oracle.decode(oracle.canonical(value))
            for text in fixture["allowed"]:
                value = copy.deepcopy(golden[entry["base"]])
                replace_path(value, entry["path"], text)
                value = oracle.seal(value)
                with self.subTest(path=entry["path"], text=text):
                    self.assertEqual(oracle.decode(oracle.encode(value)), value)
        for path in (["evidence", 0, "pointer"], ["evidence", 0, "baseline", "pointer"]):
            for text in fixture["rejected"]:
                value = copy.deepcopy(golden["regressed"])
                replace_path(value, path, text)
                with self.subTest(path=path, text=text), self.assertRaises(ValueError):
                    oracle.encode(oracle.seal(value))

    def test_board_fences_fail_before_dispatch(self):
        self.assertEqual(oracle.resolve_board(None, "sample-board", True), "sample-board")
        self.assertEqual(oracle.resolve_board("sample-board", None, False), "sample-board")
        for requested, worker, pinned in [("other-board", "sample-board", True),
                                           (None, None, True), (None, None, False),
                                           ("../board", None, False)]:
            with self.assertRaises(ValueError):
                oracle.resolve_board(requested, worker, pinned)

    def test_redaction_exact_readback_and_unknown_write_outcome(self):
        record = load("golden.json")["confirmed"]
        body = oracle.encode(record)
        self.assertEqual(oracle.readback(body, body), "verified")
        for stored in (body.replace("Workflow", "[REDACTED]"), body.replace("Workflow", "Changed"),
                       body[:80], None, 7, {}, "[hermes-outcome:v1]\n\ud800"):
            self.assertEqual(oracle.readback(body, stored), "write_unverified")

    def test_sensitive_inputs_and_opaque_url_credentials_rejected(self):
        record = load("golden.json")["confirmed"]
        for text in ("API_KEY=synthetic-secret", "Bearer synthetic-secret",
                     "-----BEGIN PRIVATE KEY-----", "password: synthetic-secret",
                     "https://example.invalid/evidence?opaque=synthetic-secret",
                     "https://user:synthetic-secret@example.invalid/evidence",
                     "https://example.invalid/evidence#synthetic-secret",
                     "file:///private/evidence", "[REDACTED]"):
            value = copy.deepcopy(record)
            value["summary"] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                oracle.encode(oracle.seal(value))

    def test_unknown_deadline_vs_supported_external_anchor(self):
        timing = load("golden.json")["contract"]["timing"]
        self.assertEqual(oracle.due(timing, {}, "2026-10-03T00:00:00Z"), "due_time_unknown")
        self.assertEqual(oracle.due(timing, {"deployment": "2026-10-01T00:00:00Z"},
                                    "2026-10-03T00:00:00Z"), "overdue")
        self.assertEqual(oracle.due(timing, {"deployment": "2026-10-01T00:00:00Z"},
                                    "2026-10-02T00:00:00Z"), "due")
        self.assertEqual(oracle.due(dict(timing, deadline="2026-10-04T00:00:00Z"), {},
                                    "2026-10-03T00:00:00Z"), "not_due")
        self.assertEqual(oracle.due(dict(timing, deadline="2026-10-04T00:00:00Z"),
                                    {"deployment": "2026-10-01T00:00:00Z"}, "2026-10-03T00:00:00Z"), "overdue")
        with self.assertRaises(ValueError):
            oracle.due(timing, {"deployment": "2026-02-30T00:00:00Z"}, "2026-10-03T00:00:00Z")

    def test_write_preflight_immutable_contract_retry_and_stale_head(self):
        golden = load("golden.json")
        rows = [oracle.occurrence(golden["contract"]), oracle.occurrence(golden["confirmed"])]
        self.assertEqual(oracle.preflight(golden["contract"], rows, "done"), "identical_retry")
        self.assertEqual(oracle.preflight(golden["confirmed"], rows, "done"), "identical_retry")
        self.assertEqual(oracle.preflight(golden["regressed"], rows, "done"), "append")
        for record, status, code in [(golden["regressed"], "review", "unfinished_task"),
                                     (dict(golden["contract"], objective="different"), "done", "conflict"),
                                     (golden["partial"], "done", "stale_predecessor")]:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                oracle.preflight(oracle.seal(record), rows, status)


class ArchitectureTests(unittest.TestCase):
    def test_spec_is_data_only_and_calls_are_allowlisted(self):
        oracle.audit_spec()
        self.assertEqual(set(oracle.POLICY["allowed_native_tools"]), {"kanban_show", "kanban_comment"})
        self.assertEqual(oracle.POLICY["read_tools"], ["outcome_show", "outcome_check"])
        self.assertFalse(oracle.POLICY["completion_hook"])
        self.assertFalse(oracle.POLICY["automatic_followup"])
        self.assertFalse(oracle.POLICY["persistent_cache"])

    def test_complete_acceptance_mapping_names_existing_tests(self):
        mapping = load("acceptance-map.json")
        names = {name for cls in (SchemaTests, HistoryTests, AdmissionTests, ArchitectureTests)
                 for name in dir(cls) if name.startswith("test_")}
        self.assertEqual(set(mapping), set(oracle.POLICY["acceptance_boundaries"]))
        for boundary, entry in mapping.items():
            with self.subTest(boundary=boundary):
                self.assertTrue(entry["schema_tests"])
                self.assertLessEqual(set(entry["schema_tests"]), names)
                self.assertTrue(entry["production_gate"])
