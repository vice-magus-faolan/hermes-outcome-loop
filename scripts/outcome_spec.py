# SPDX-License-Identifier: GPL-3.0-or-later
"""Executable, data-only ADR oracle. NOT a production parser or Kanban adapter.

JSON Schema covers record shape; named checks cover contextual invariants. The
closed registry never fetches schemas. No native tool or evidence I/O occurs.
Downstream production tests must exercise their own code against these fixtures.
"""
from __future__ import annotations

import ast
from collections import defaultdict
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "schemas/protocol.json").read_text(encoding="utf-8"))
MARKER = POLICY["marker"]


def no_remote(uri: str):
    """Unknown references are errors, never network requests."""
    raise NoSuchResource(ref=uri)


def schemas() -> dict:
    """Load only the three fixed repository schema files."""
    return {name: json.loads((ROOT / f"schemas/{name}.schema.json").read_text(encoding="utf-8"))
            for name in ("common", "contract", "observation")}


def validators() -> dict:
    values = schemas()
    checker = FormatChecker()

    @checker.checks("date-time", raises=ValueError)
    def utc_seconds(value):
        if not isinstance(value, str):
            return True  # Type errors belong to the schema's type constraint.
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return True

    registry = Registry(retrieve=no_remote).with_resources(
        (value["$id"], Resource.from_contents(value)) for value in values.values())
    return {name: Draft202012Validator(value, registry=registry, format_checker=checker)
            for name, value in values.items() if name != "common"}


VALIDATORS = validators()


def check_schemas() -> None:
    """Validate Draft 2020-12 metaschemas and reject unresolved references."""
    values = schemas()
    for value in values.values():
        Draft202012Validator.check_schema(value)
    allowed = {value["$id"].rsplit("/", 1)[-1] for value in values.values()}
    for value in values.values():
        check_refs(value, allowed)


def check_refs(value: object, allowed: set[str]) -> None:
    if isinstance(value, dict):
        if "$ref" in value:
            target = value["$ref"].split("#", 1)[0]
            if target and target not in allowed:
                raise ValueError("nonlocal_schema_reference")
        for child in value.values():
            check_refs(child, allowed)
    elif isinstance(value, list):
        for child in value:
            check_refs(child, allowed)


def admit_text(text: str) -> None:
    """Reject known secrets/unsafe pointers, not claim universal secret detection."""
    text.encode("utf-8", errors="strict")
    if any(ord(character) < 32 for character in text):
        raise ValueError("control_character")
    sensitive = r"(?i)(?:\b(?:[a-z_]*api[_-]?key|[a-z_]*token|password|secret)\s*[:=]|\bbearer\s|-----BEGIN .*PRIVATE KEY-----|\[REDACTED\]|\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+)"
    if re.search(sensitive, text):
        raise ValueError("sensitive_input")
    # A scheme need not have // (data:, file:, urn:, mailto:). Token boundaries
    # keep ISO timestamps/clock times and spaced prose labels out of this grammar.
    for url in re.findall(r"(?<![A-Za-z0-9+._-])[A-Za-z][A-Za-z0-9+.-]*:[^\s]+", text):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("unsafe_pointer")
        if not re.fullmatch(schemas()["common"]["$defs"]["pointer"]["pattern"], url):
            raise ValueError("unsafe_pointer")


def admit_values(value: object, depth: int = 0) -> None:
    if depth > 12:
        raise ValueError("nesting_limit")
    if isinstance(value, str):
        admit_text(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            admit_text(key)
            admit_values(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            admit_values(child, depth + 1)
    elif isinstance(value, float):
        raise ValueError("noninteger_number")


def validate(record: dict) -> None:
    if not isinstance(record, dict) or record.get("type") not in VALIDATORS:
        raise ValueError("malformed_record")
    if type(record.get("version")) is not int or record["version"] != 1:
        raise ValueError("unsupported_version")
    errors = list(VALIDATORS[record["type"]].iter_errors(record))
    if errors:
        raise ValueError("malformed_record")
    admit_values(record)
    if seal(record)["payload_sha256"] != record["payload_sha256"]:
        raise ValueError("integrity_mismatch")
    if record["type"] == "contract":
        ids = [criterion["id"] for criterion in record["criteria"]]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_criterion")


def payload_json(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def seal(record: dict) -> dict:
    """Generate a corruption checksum, not an identity or authentication token."""
    value = copy.deepcopy(record)
    value.pop("payload_sha256", None)
    checksum = hashlib.sha256(payload_json(value).encode("utf-8")).hexdigest()
    value["payload_sha256"] = checksum
    return value


def canonical(record: dict) -> str:
    return MARKER + payload_json(record)


def encode(record: dict) -> str:
    """Produce sorted compact UTF-8 JSON, never truncate an oversized record."""
    validate(record)
    body = canonical(record)
    if len(body.encode("utf-8")) > POLICY["max_record_bytes"]:
        raise ValueError("record_limit")
    return body


def unique_pairs(pairs: list) -> dict:
    value = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = child
    return value


def reject_constant(value: str):
    raise ValueError("nonfinite_number")


def decode(body: str) -> dict:
    if not isinstance(body, str):
        raise ValueError("malformed_record")
    if not body.startswith(MARKER):
        raise ValueError("unsupported_version")
    if len(body.encode("utf-8")) > POLICY["max_record_bytes"]:
        raise ValueError("record_limit")
    try:
        record = json.loads(body[len(MARKER):], object_pairs_hook=unique_pairs,
                            parse_constant=reject_constant)
        validate(record)
    except (RecursionError, TypeError) as error:
        raise ValueError("malformed_record") from error
    return record


def occurrence(record: dict, author: str = "profile-a", time: int = 1) -> dict:
    return {"body": encode(record), "author": author, "created_at": time}


def utf8_length(value: object) -> int | None:
    """Return a safe byte count without echoing malformed native text."""
    if not isinstance(value, str):
        return None
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeError:
        return None


def inspect_native(rows: list[object]) -> tuple[list[dict], set[str]]:
    """Validate every row, including unrelated comments, before record parsing."""
    admitted, diagnostics, total = [], set(), 0
    for row in rows:
        if not isinstance(row, dict):
            diagnostics.add("malformed_native_response")
            continue
        size = utf8_length(row.get("body"))
        if size is None:
            diagnostics.add("malformed_native_response")
            continue
        total += size  # Count valid bodies even when their provenance is unusable.
        author, created = row.get("author"), row.get("created_at")
        if not provenance_valid(author, created):
            diagnostics.add("missing_provenance")
            continue
        admitted.append(row)
    if len(rows) > POLICY["max_comments"] or total > POLICY["max_history_bytes"]:
        diagnostics.add("history_limit")
    return admitted, diagnostics


def provenance_valid(author: object, created: object) -> bool:
    return (isinstance(author, str) and bool(author.strip()) and utf8_length(author) is not None
            and type(created) is int and created >= 0)


def group(rows: list[dict], board: str, task_id: str) -> tuple:
    """Retain all admitted occurrences and distinct payload variants, no winner."""
    records, sources, diagnostics = defaultdict(list), defaultdict(list), set()
    for row in rows:
        body = row["body"]
        if not body.startswith("[hermes-outcome:"):
            continue
        try:
            value = decode(body)
        except ValueError as error:
            diagnostics.add(str(error) if str(error) in {"unsupported_version", "record_limit", "integrity_mismatch"} else "malformed_record")
            continue
        identifier = value["record_id"]
        sources[identifier].append(copy.deepcopy(row))
        if (value["board"], value["task_id"]) != (board, task_id):
            diagnostics.add("target_mismatch")
        if value not in records[identifier]:
            records[identifier].append(value)
        if len(records[identifier]) > 1:
            diagnostics.add("conflicting_payload")
    return dict(records), dict(sources), diagnostics


def graph(records: dict) -> tuple[set[str], list[str]]:
    """Diagnose union edges; only single-variant groups can yield a chain."""
    diagnostics, children = set(), defaultdict(set)
    for identifier, variants in records.items():
        for value in variants:
            predecessor = value["predecessor"]
            children[predecessor].add(identifier)
            if predecessor is not None and predecessor not in records:
                diagnostics.add("missing_predecessor")
    if any(len(ids) > 1 for ids in children.values()):
        diagnostics.add("fork")
    if has_cycle(records, children):
        diagnostics.add("cycle")
    chain = []
    if any(len(variants) > 1 for variants in records.values()):
        return diagnostics, chain
    current = children.get(None, set())
    while len(current) == 1 and not diagnostics:
        identifier = next(iter(current))  # Singleton, never a winner-selection rule.
        chain.append(identifier)
        current = children.get(identifier, set())
    return diagnostics, chain


def has_cycle(records: dict, children: dict) -> bool:
    """Peel the union graph iteratively; conflicts can supply multiple parents."""
    incoming = dict.fromkeys(records, 0)
    for parent, identifiers in children.items():
        if parent in records:
            for identifier in identifiers:
                incoming[identifier] += 1
    ready = [identifier for identifier, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        parent = ready.pop()
        visited += 1
        for identifier in children.get(parent, set()):
            incoming[identifier] -= 1
            if incoming[identifier] == 0:
                ready.append(identifier)
    return visited != len(records)


def evidence_valid(contract: dict, value: dict) -> bool:
    criteria = {row["id"]: row for row in contract["criteria"]}
    entries = value["evidence"]
    ids = [row["criterion_id"] for row in entries]
    if len(ids) != len(set(ids)) or set(ids) != set(criteria):
        return False
    if contract["requires_artifact"] and value["artifact"] is None:
        return False
    for row in entries:
        needs_baseline = criteria[row["criterion_id"]]["requires_baseline"]
        needs_baseline |= value["result"] == "regressed" and row["finding"] == "contradicted"
        if needs_baseline and row["finding"] != "unknown" and row["baseline"] is None:
            return False
    findings = {row["finding"] for row in entries}
    result_rules = {
        "confirmed": findings == {"supported"},
        "partially_confirmed": "supported" in findings and len(findings) > 1,
        "not_confirmed": "contradicted" in findings,
        "regressed": "contradicted" in findings,
        "inconclusive": "unknown" in findings and "contradicted" not in findings,
    }
    return result_rules[value["result"]]


def contextual(contracts: dict, observations: dict, chain: list[str], status: str) -> set[str]:
    """Union evidence/binding errors over variants; never pick a representative."""
    diagnostics = set()
    if observations and status != "done":
        diagnostics.add("observations_on_unfinished")
    if len(contracts) != 1:
        return diagnostics | ({"orphan_observation"} if observations else set())
    contract_id, candidates = next(iter(contracts.items()))  # Sole logical identity.
    for variants in observations.values():
        for value in variants:
            if value["contract_id"] != contract_id:
                diagnostics.add("orphan_observation")
            elif any(not evidence_valid(contract, value) for contract in candidates):
                diagnostics.add("invalid_evidence")
    diagnostics.update(regression_errors(observations, chain))
    return diagnostics


def regression_errors(observations: dict, chain: list[str]) -> set[str]:
    """Ancestry comparisons require an unambiguous complete observation chain."""
    diagnostics = set()
    ancestors = set()
    for identifier in chain:
        value = observations[identifier][0]  # graph() only returns single-variant chains.
        if value["result"] == "regressed":
            reference = value["regression_of"]
            if reference not in ancestors or observations[reference][0]["result"] not in {"confirmed", "partially_confirmed"}:
                diagnostics.add("invalid_regression")
            elif not regression_criteria_valid(observations[reference][0], value):
                diagnostics.add("invalid_regression")
        ancestors.add(identifier)
    return diagnostics


def regression_criteria_valid(previous: dict, current: dict) -> bool:
    supported = {row["criterion_id"] for row in previous["evidence"] if row["finding"] == "supported"}
    contradicted = {row["criterion_id"] for row in current["evidence"] if row["finding"] == "contradicted"}
    return contradicted <= supported


def result(state: str, diagnostics: set[str], sources: dict, latest: str | None = None) -> dict:
    actions = {"invalid_history": "HISTORY_ATTENTION", "awaiting_observation": "OBSERVATION_REQUIRED",
               "untracked": "NO_ACTION_REQUIRED", "planned": "NO_ACTION_REQUIRED", "confirmed": "NO_ACTION_REQUIRED"}
    return {"state": state, "diagnostics": sorted(diagnostics), "latest": latest,
            "occurrences": sources, "action": actions.get(state, "FOLLOWUP_SUGGESTED")}


def reconstruct(rows: object, status: str, board: str, task_id: str) -> dict:
    """Apply invalid > empty > unfinished > unobserved > unique-head precedence."""
    if not isinstance(rows, list):
        return result("invalid_history", {"malformed_native_response"}, {})
    admitted, diagnostics = inspect_native(rows)
    if "history_limit" in diagnostics:
        return result("invalid_history", diagnostics, {})
    records, sources, record_errors = group(admitted, board, task_id)
    diagnostics.update(record_errors)
    contracts = {key: variants for key, variants in records.items() if key.startswith("oc_")}
    observations = {key: variants for key, variants in records.items() if key.startswith("oo_")}
    if len(contracts) > 1:
        diagnostics.add("multiple_contracts")
    graph_errors, chain = graph(observations)
    diagnostics.update(graph_errors)
    diagnostics.update(contextual(contracts, observations, chain, status))
    if diagnostics:
        return result("invalid_history", diagnostics, sources)
    if not contracts:
        return result("untracked", set(), sources)
    if status != "done":
        return result("planned", set(), sources)
    if not chain:
        return result("awaiting_observation", set(), sources)
    latest = chain[-1]
    return result(observations[latest][0]["result"], set(), sources, latest)


def evaluate_case(case: dict, golden: dict) -> dict:
    rows = []
    for entry in case["records"]:
        value = copy.deepcopy(golden[entry if isinstance(entry, str) else entry["base"]])
        if isinstance(entry, dict):
            value.update(entry["set"])
        rows.append(occurrence(seal(value)))
    return reconstruct(rows, case["status"], "sample-board", "sample-root")


def resolve_board(requested: str | None, ambient: str | None, pinned: bool) -> str:
    """Require an explicit board or a verifiable worker slug; never infer a path."""
    if pinned and (not ambient or requested not in (None, ambient)):
        raise ValueError("board_fence")
    board = requested or (ambient if pinned else None)
    if not isinstance(board, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", board):
        raise ValueError("board_required")
    return board


def readback(expected: str, stored: str | None) -> str:
    """A byte-identical stored record is necessary, not sufficient, for success."""
    if stored is None:
        return "write_unverified"
    try:
        decode(stored)
    except ValueError:
        return "write_unverified"
    return "verified" if stored == expected else "write_unverified"


def timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise ValueError("invalid_timestamp")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def due(timing: dict, anchors: dict, now: str) -> str:
    """Compare elapsed durations without constructing an overflowing due date."""
    current = timestamp(now)
    lateness = []
    if timing["deadline"]:
        lateness.append(current - timestamp(timing["deadline"]))
    anchor = anchors.get(timing["anchor"])
    if anchor:
        lateness.append(current - timestamp(anchor) - timedelta(seconds=timing["delay_seconds"]))
    if not lateness:
        return "due_time_unknown"
    latest = max(lateness)
    if latest == timedelta(0):
        return "due"
    return "overdue" if latest > timedelta(0) else "not_due"


def preflight(record: dict, rows: list[dict], status: str) -> str:
    """Specify admission, not atomic insertion or a dispatch implementation."""
    encode(record)
    if record["type"] == "observation" and status != "done":
        raise ValueError("unfinished_task")
    history = reconstruct(rows, status, record["board"], record["task_id"])
    if history["state"] == "invalid_history":
        raise ValueError("invalid_history")
    records = {decode(row["body"])["record_id"]: decode(row["body"]) for row in rows
               if row["body"].startswith(MARKER)}
    existing = records.get(record["record_id"])
    if existing is not None:
        if existing != record:
            raise ValueError("conflict")
        return "identical_retry"
    if record["type"] == "contract" and records:
        raise ValueError("conflict")
    if record["type"] == "observation" and record["predecessor"] != history["latest"]:
        raise ValueError("stale_predecessor")
    proposed = reconstruct(rows + [occurrence(record)], status, record["board"], record["task_id"])
    if proposed["state"] == "invalid_history":
        raise ValueError("invalid_history")
    return "append"


def audit_spec() -> None:
    """Constrain this oracle, not all plugin Python, to data-only operations."""
    tree = ast.parse((ROOT / "scripts/outcome_spec.py").read_text(encoding="utf-8"))
    allowed = {"__future__", "ast", "collections", "copy", "datetime", "hashlib", "json", "pathlib", "re", "urllib.parse",
               "jsonschema", "referencing", "referencing.exceptions"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name not in allowed for alias in node.names):
                raise ValueError("forbidden_spec_import")
        elif isinstance(node, ast.ImportFrom) and node.module not in allowed:
            raise ValueError("forbidden_spec_import")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"write_text", "write_bytes", "open", "dispatch_tool", "execute", "connect"}:
                raise ValueError("forbidden_spec_effect")
