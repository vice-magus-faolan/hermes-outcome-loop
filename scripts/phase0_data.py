# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic redaction corpus and padded-thread bounds, through actual native tools."""
from collections import Counter
import json

from phase0_extended import logical, require, cost
from phase0_ordering import MARKER, MAX_BYTES, MAX_HISTORY_BYTES, reconstruct
from phase0_snapshot import snapshot


def new_body(before, after):
    """Identify exactly one added body without assuming returned tie ordering."""
    delta = Counter(item["body"] for item in after) - Counter(item["body"] for item in before)
    require(sum(delta.values()) == 1, "native append delta is ambiguous")
    return next(iter(delta))


def stored_equals_public(base, task, comments):
    """Compare native stored history to public read, not output masking artifacts."""
    native = snapshot(base, task)["comments"]
    fields = ("author", "body", "created_at")
    require(Counter(tuple(row[key] for key in fields) for row in native) ==
            Counter(tuple(row[key] for key in fields) for row in comments), "stored/public comment history mismatch")


def redaction_corpus(call, create, base):
    task = create()
    synthetic = "sk-" + "SYNTHETIC_NOT_A_SECRET_1234567890"
    corpus = {
        "unicode_quotes_safe": logical("safe", summary='caf\u00e9 \"quoted\"\n evidence'),
        "provider_summary": logical("provider", summary=synthetic),
        "github_summary": logical("github", summary="ghp_" + "SYNTHETICNOTASECRET1234567890"),
        "signed_url": logical("url", summary="https://example.invalid/evidence?token=syntheticopaque1234567890"),
        "env_assignment": logical("env", summary="API_KEY=syntheticopaque1234567890"),
        "sensitive_record_id": logical(synthetic),
        "sensitive_contract_id": logical("contract").replace("probe-contract", synthetic),
        "sensitive_predecessor": logical("predecessor", synthetic),
    }
    results = []
    for name, body in corpus.items():
        before = call("kanban_show", task_id=task, board="phase0")["comments"]
        call("kanban_comment", task_id=task, board="phase0", body=body)
        after = call("kanban_show", task_id=task, board="phase0")["comments"]
        stored_equals_public(base, task, after)
        stored = new_body(before, after)
        reply = call("bounded_append", task_id=task, board="phase0", body=body, allow_error=True)
        policy_after = call("kanban_show", task_id=task, board="phase0")["comments"]
        changed = stored != body
        parseable = True
        try:
            decoded = json.loads(stored[len(MARKER):])
        except ValueError:
            decoded, parseable = {}, False
        if name == "unicode_quotes_safe":
            require(not changed and parseable and reply.get("exact_stored_readback"), "safe Unicode roundtrip failed")
        elif name == "signed_url":
            require(not changed and "error" in reply and policy_after == after,
                    "URL-query limitation not compensated by pre-write rejection")
        else:
            require(changed and "error" in reply, "sensitive mutation acknowledged unchanged: " + name)
        results.append({"case": name, "stored_changed": changed, "json_parseable": parseable,
                        "identifier_changed": parseable and any(decoded.get(key) != json.loads(body[len(MARKER):])[key]
                            for key in ("record_id", "contract_id", "predecessor")),
                        "success_acknowledged": "error" not in reply,
                        "policy_rejected_before_write": policy_after == after})
    before = call("kanban_show", task_id=task, board="phase0")
    for arguments in ({"body": "   "}, {"body": logical("forged"), "author": "forged-profile"}):
        reply = call("kanban_comment", task_id=task, board="phase0", allow_error=True, **arguments)
        require("error" in reply, "blank or caller-author field accepted")
    after = call("kanban_show", task_id=task, board="phase0")
    require(all(before[key] == after[key] for key in ("task", "runs", "events", "comments")),
            "redaction rejection mutated native history")
    return {"passed": True, "cases": results, "caller_author_rejected": True, "blank_rejected": True,
            "raw_stored_history_matches_public_read": True,
            "cli_difference_evidence": "installed public CLI source inspection, no CLI write fallback"}


def padded_scaling(call, create):
    task = create()
    previous = None
    for index in range(MAX_HISTORY_BYTES // MAX_BYTES):
        identifier = f"padded-{index}"
        envelope = logical(identifier, previous, "x")
        body = logical(identifier, previous, "x" * (MAX_BYTES - len(envelope.encode()) + 1))
        require(len(body.encode()) == MAX_BYTES, "padded record byte boundary drift")
        call("kanban_comment", task_id=task, board="phase0", body=body)
        previous = identifier
    measure = cost(call, task)
    rows = call("kanban_show", task_id=task, board="phase0")["comments"]
    require(sum(len(row["body"].encode()) for row in rows) == MAX_HISTORY_BYTES,
            "padded history boundary mismatch")
    require(reconstruct(rows)["latest"] == previous, "padded chain head missing")
    call("kanban_comment", task_id=task, board="phase0", body=logical("byte-overflow", previous))
    require(reconstruct(call("kanban_show", task_id=task, board="phase0")["comments"])["diagnostics"] == ["history_byte_limit"],
            "byte-budget overflow not visible")
    return {"passed": True, "total_record_bytes": MAX_HISTORY_BYTES, "record_bytes": MAX_BYTES,
            "measurement": measure, "history_byte_overflow_visible": True}
