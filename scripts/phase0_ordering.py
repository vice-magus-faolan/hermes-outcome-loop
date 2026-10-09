# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, data-only predecessor experiment, NOT the production outcome schema.

Never resolve a fork with source positions, native times or sorted IDs. Preserve
all occurrences even when identical payloads come from different native authors.
"""
from __future__ import annotations

import json

MARKER = "[hermes-outcome:probe-v1]\n"
MAX_RECORDS = 1024
MAX_BYTES = 16384
MAX_HISTORY_BYTES = 2 * 1024 * 1024


def decode(comment: dict) -> dict:
    """Accept only the small experimental envelope, within explicit bounds."""
    body = comment["body"]
    if not body.startswith(MARKER) or len(body.encode("utf-8")) > MAX_BYTES:
        raise ValueError("unsupported or oversized probe record")
    value = json.loads(body[len(MARKER):])
    if set(value) != {"record_id", "contract_id", "predecessor", "summary"}:
        raise ValueError("invalid probe shape")
    if not all(isinstance(value[key], str) and value[key]
               for key in ("record_id", "contract_id", "summary")):
        raise ValueError("invalid probe fields")
    predecessor = value["predecessor"]
    if predecessor is not None and (not isinstance(predecessor, str) or not predecessor):
        raise ValueError("invalid predecessor")
    if not isinstance(comment["author"], str) or not isinstance(comment["created_at"], int):
        raise ValueError("missing native provenance")
    return value


def group(comments: list[dict]) -> tuple[dict, dict, set[str]]:
    """Group identical retries without erasing source attribution or conflicts."""
    records, occurrences, diagnostics = {}, {}, set()
    for comment in comments:
        try:
            value = decode(comment)
        except (KeyError, ValueError, TypeError, AttributeError):
            diagnostics.add("unreadable_record")
            continue
        identifier = value["record_id"]
        occurrences.setdefault(identifier, []).append(comment)
        if identifier in records and records[identifier] != value:
            diagnostics.add("conflict")
        else:
            records[identifier] = value
    return records, occurrences, diagnostics


def has_cycle(records: dict) -> bool:
    """Follow parent pointers iteratively; no recursion limit or timestamp order."""
    finished = set()
    for identifier in records:
        active = set()
        current = identifier
        while current in records and current not in finished:
            if current in active:
                return True
            active.add(current)
            current = records[current]["predecessor"]
        finished.update(active)
    return False


def graph_diagnostics(records: dict) -> tuple[set[str], dict]:
    """Check roots, contract identity, missing links, branches and cycles."""
    diagnostics, children = set(), {}
    if len({value["contract_id"] for value in records.values()}) > 1:
        diagnostics.add("mixed_contracts")
    for identifier, value in records.items():
        predecessor = value["predecessor"]
        children.setdefault(predecessor, []).append(identifier)
        if predecessor is not None and predecessor not in records:
            diagnostics.add("missing_predecessor")
    if len(children.get(None, [])) > 1:
        diagnostics.add("multiple_roots")
    if any(len(ids) > 1 for predecessor, ids in children.items() if predecessor is not None):
        diagnostics.add("fork")
    if has_cycle(records):
        diagnostics.add("cycle")
    return diagnostics, children


def reconstruct(comments: list[dict]) -> dict:
    """Return a unique chain head only for unambiguous readable bounded history."""
    if len(comments) > MAX_RECORDS:
        return {"latest": None, "diagnostics": ["history_limit"], "occurrences": {}}
    total = sum(len(row.get("body", "").encode("utf-8")) for row in comments
                if isinstance(row.get("body"), str))
    if total > MAX_HISTORY_BYTES:
        return {"latest": None, "diagnostics": ["history_byte_limit"], "occurrences": {}}
    records, occurrences, diagnostics = group(comments)
    graph_errors, children = graph_diagnostics(records)
    diagnostics.update(graph_errors)
    heads = [identifier for identifier in records if identifier not in children]
    latest = heads[0] if not diagnostics and len(heads) == 1 else None
    return {"latest": latest, "diagnostics": sorted(diagnostics), "occurrences": occurrences}
