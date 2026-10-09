# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure reconstruction of bounded native records. No ordering by source position.

Every admitted retry and conflicting variant survives. Only an unambiguous causal
chain yields a head. Unknown native metadata is ignored, never executed or echoed.
"""
from __future__ import annotations

from collections import defaultdict
import copy

from .records import (MAX_COMMENTS, MAX_HISTORY_BYTES, OutcomeError, decode,
                      timestamp, utf8_length)


def native_rows(rows: object) -> tuple[list[dict], set[str]]:
    """Validate native bodies/provenance, including ordinary comments, before parsing."""
    if not isinstance(rows, list):
        return [], {"malformed_native_response"}
    admitted, diagnostics, total = [], set(), 0
    for row in rows:
        if not isinstance(row, dict):
            diagnostics.add("malformed_native_response")
            continue
        size = utf8_length(row.get("body"))
        if size is None:
            diagnostics.add("malformed_native_response")
            continue
        total += size
        author, created = row.get("author"), row.get("created_at")
        if not valid_provenance(author, created):
            diagnostics.add("missing_provenance")
            continue
        admitted.append({key: row[key] for key in ("body", "author", "created_at")})
    if len(rows) > MAX_COMMENTS or total > MAX_HISTORY_BYTES:
        diagnostics.add("history_limit")
    return admitted, diagnostics


def valid_provenance(author: object, created: object) -> bool:
    return (isinstance(author, str) and bool(author.strip()) and utf8_length(author) is not None
            and type(created) is int and created >= 0)


def collect(rows: list[dict], board: str, task_id: str) -> tuple[dict, dict, set[str]]:
    variants, occurrences, diagnostics = defaultdict(list), defaultdict(list), set()
    for row in rows:
        if not row["body"].startswith("[hermes-outcome:"):
            continue
        try:
            value = decode(row["body"])
        except OutcomeError as error:
            code = str(error)
            diagnostics.add(code if code in {"unsupported_version", "integrity_mismatch", "record_limit"} else "malformed_record")
            continue
        identifier = value["record_id"]
        occurrences[identifier].append(copy.deepcopy(row))
        if value not in variants[identifier]:
            variants[identifier].append(value)
        if len(variants[identifier]) > 1:
            diagnostics.add("conflicting_payload")
        if (value["board"], value["task_id"]) != (board, task_id):
            diagnostics.add("target_mismatch")
    return dict(variants), dict(occurrences), diagnostics


def topology(observations: dict) -> tuple[list[str], set[str]]:
    """Use all-variant union edges for errors; never choose a conflicting payload."""
    children, diagnostics = defaultdict(set), set()
    for identifier, variants in observations.items():
        for value in variants:
            parent = value["predecessor"]
            children[parent].add(identifier)
            if parent is not None and parent not in observations:
                diagnostics.add("missing_predecessor")
    if any(len(ids) > 1 for ids in children.values()):
        diagnostics.add("fork")
    if cyclic(observations, children):
        diagnostics.add("cycle")
    chain = []
    if diagnostics or any(len(values) != 1 for values in observations.values()):
        return chain, diagnostics
    candidates = children.get(None, set())
    while len(candidates) == 1:
        identifier = next(iter(candidates))  # Singleton is a causal fact, not a sort winner.
        chain.append(identifier)
        candidates = children.get(identifier, set())
    return chain, diagnostics


def cyclic(observations: dict, children: dict) -> bool:
    """Iterative topological peeling avoids recursion at the history cap."""
    indegree = dict.fromkeys(observations, 0)
    for parent, ids in children.items():
        if parent in observations:
            for identifier in ids:
                indegree[identifier] += 1
    ready = [identifier for identifier, degree in indegree.items() if degree == 0]
    count = 0
    while ready:
        parent = ready.pop()
        count += 1
        for identifier in children.get(parent, set()):
            indegree[identifier] -= 1
            if indegree[identifier] == 0:
                ready.append(identifier)
    return count != len(observations)


def evidence_matches(contract: dict, observation: dict) -> bool:
    criteria = {row["id"]: row for row in contract["criteria"]}
    evidence = observation["evidence"]
    ids = [row["criterion_id"] for row in evidence]
    if len(ids) != len(set(ids)) or set(ids) != set(criteria):
        return False
    if contract["requires_artifact"] and observation["artifact"] is None:
        return False
    for row in evidence:
        required = criteria[row["criterion_id"]]["requires_baseline"]
        required |= observation["result"] == "regressed" and row["finding"] == "contradicted"
        if required and row["finding"] != "unknown" and row["baseline"] is None:
            return False
    findings = {row["finding"] for row in evidence}
    rules = {
        "confirmed": findings == {"supported"},
        "partially_confirmed": "supported" in findings and len(findings) > 1,
        "not_confirmed": "contradicted" in findings,
        "regressed": "contradicted" in findings,
        "inconclusive": "unknown" in findings and "contradicted" not in findings,
    }
    return rules[observation["result"]]


def valid_regression(previous: dict, current: dict) -> bool:
    if previous["result"] not in {"confirmed", "partially_confirmed"}:
        return False
    supported = {row["criterion_id"] for row in previous["evidence"] if row["finding"] == "supported"}
    contradicted = {row["criterion_id"] for row in current["evidence"] if row["finding"] == "contradicted"}
    return contradicted <= supported


def regression_diagnostics(observations: dict, chain: list[str]) -> set[str]:
    diagnostics, ancestors = set(), {}
    for identifier in chain:
        value = observations[identifier][0]  # Only topology's unambiguous chain reaches here.
        if value["result"] == "regressed":
            earlier = ancestors.get(value["regression_of"])
            if earlier is None or not valid_regression(earlier, value):
                diagnostics.add("invalid_regression")
        ancestors[identifier] = value
    return diagnostics


def contextual(contracts: dict, observations: dict, chain: list[str], status: str,
               completed_at: str | None) -> set[str]:
    diagnostics = set()
    if observations and status != "done":
        diagnostics.add("observations_on_unfinished")
    for variants in observations.values():
        for value in variants:
            if completed_at is not None and timestamp(value["observed_at"]) < timestamp(completed_at):
                diagnostics.add("invalid_evidence")
    if len(contracts) != 1:
        return diagnostics | ({"orphan_observation"} if observations else set())
    contract_id, contracts = next(iter(contracts.items()))
    for variants in observations.values():
        for value in variants:
            if value["contract_id"] != contract_id:
                diagnostics.add("orphan_observation")
            elif any(not evidence_matches(contract, value) for contract in contracts):
                diagnostics.add("invalid_evidence")
    return diagnostics | regression_diagnostics(observations, chain)


def derived_state(diagnostics: set[str], contracts: dict, chain: list[str],
                  observations: dict, status: str) -> str:
    if diagnostics:
        return "invalid_history"
    if not contracts:
        return "untracked"
    if status != "done":
        return "planned"
    return observations[chain[-1]][0]["result"] if chain else "awaiting_observation"


def present(state: str, diagnostics: set[str], variants: dict, sources: dict,
            chain: list[str], board: str, task_id: str, status: str) -> dict:
    contracts = [values[0] for key, values in variants.items() if key.startswith("oc_") and len(values) == 1]
    latest = chain[-1] if chain and not diagnostics else None
    head = variants[latest][0] if latest else None
    contract = contracts[0] if len(contracts) == 1 and not diagnostics else None
    actions = {"invalid_history": "HISTORY_ATTENTION", "awaiting_observation": "OBSERVATION_REQUIRED",
               "untracked": "NO_ACTION_REQUIRED", "planned": "NO_ACTION_REQUIRED", "confirmed": "NO_ACTION_REQUIRED"}
    action = actions.get(state, "FOLLOWUP_SUGGESTED")
    suggestions = {"HISTORY_ATTENTION": "Inspect history diagnostics; no automatic reconciliation.",
                   "OBSERVATION_REQUIRED": "Perform the declared post-delivery observations.",
                   "FOLLOWUP_SUGGESTED": "Investigate gaps or regression, or collect missing evidence; explicitly create native follow-up work if needed."}
    return copy.deepcopy({
        "board": board, "task_id": task_id, "kanban_status": status, "delivery_done": status == "done",
        "state": state, "diagnostics": sorted(diagnostics), "contract": contract,
        "variants": variants, "occurrences": sources, "chain": chain if not diagnostics else [],
        "observations": [variants[identifier][0] for identifier in chain] if not diagnostics else [],
        "latest": latest, "head": head, "latest_evidence": head["evidence"] if head else [],
        "residual_risk": head["residual_risk"] if head else [], "action": action,
        "suggestion": suggestions.get(action), "timing": contract["timing"] if contract else None,
    })


def reconstruct(rows: object, status: str, board: str, task_id: str,
                completed_at: str | None = None) -> dict:
    """Return all diagnostics and source occurrences; invalidity suppresses success."""
    admitted, diagnostics = native_rows(rows)
    if "history_limit" in diagnostics:
        return present("invalid_history", diagnostics, {}, {}, [], board, task_id, status)
    variants, sources, errors = collect(admitted, board, task_id)
    diagnostics.update(errors)
    contracts = {key: values for key, values in variants.items() if key.startswith("oc_")}
    observations = {key: values for key, values in variants.items() if key.startswith("oo_")}
    if len(contracts) > 1:
        diagnostics.add("multiple_contracts")
    chain, graph_errors = topology(observations)
    diagnostics.update(graph_errors)
    diagnostics.update(contextual(contracts, observations, chain, status, completed_at))
    state = derived_state(diagnostics, contracts, chain, observations, status)
    return present(state, diagnostics, variants, sources, chain, board, task_id, status)
