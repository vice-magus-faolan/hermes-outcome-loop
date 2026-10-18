# SPDX-License-Identifier: GPL-3.0-or-later
"""Failure and actual parallel-process native cases, not transport mocks."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import time

from native_support import require
from native_snapshot import snapshot, preserved


def ordinary_delivery(api, task):
    api.native("kanban_request_review", task_id=task, board="outcome-test", summary="Native work survives outcome failure")
    api.complete(task)


def recompletion_case(api):
    """Preserve admitted v1 bytes through an actual native reopen and new delivery."""
    from plugins.kanban.dashboard.plugin_api import UpdateTaskBody, update_task

    task = api.create()
    require(api.outcome("outcome_define", task, api.payload("contract", task))["ok"], "definition failed")
    api.complete(task)
    confirmed = api.payload("confirmed", task)
    require(api.outcome("outcome_observe", task, confirmed)["ok"], "confirmation failed")
    correction = api.payload("regressed", task)
    require(api.outcome("outcome_observe", task, correction)["ok"], "correction failed")
    original = api.native("kanban_show", task_id=task, board="outcome-test")
    require(update_task(task, UpdateTaskBody(status="ready"), board="outcome-test")["task"]["status"] == "ready",
            "native reopen failed")
    require(api.outcome("outcome_observe", task, confirmed)["error"] == "unfinished_task",
            "reopened retry admitted")
    # Native timestamps have one-second resolution; establish a genuinely later anchor.
    while int(time.time()) <= max(original["task"]["completed_at"], original["comments"][-1]["created_at"]):
        time.sleep(0.01)
    api.complete(task)
    delivered = api.native("kanban_show", task_id=task, board="outcome-test")
    require(delivered["task"]["completed_at"] > original["task"]["completed_at"], "completion anchor did not advance")
    require(delivered["comments"] == original["comments"], "recompletion rewrote outcome history")
    view = api.outcome("outcome_show", task)["view"]
    require(view["state"] == "regressed" and len(view["observations"]) == 2,
            "recompletion poisoned previously admitted observations")
    for value in (confirmed, correction):
        require(api.outcome("outcome_observe", task, value).get("acknowledgment") == "identical_retry",
                "historical exact retry was not read-only")
    recovery = api.payload("confirmed", task)
    recovery.update(record_id="oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", predecessor=correction["record_id"])
    backdated = dict(recovery, observed_at=confirmed["observed_at"])
    require(api.outcome("outcome_observe", task, backdated).get("error") == "pre_delivery_observation",
            "new backdated recovery admitted")
    conflict = dict(confirmed, summary="Conflicting historical payload")
    require(api.outcome("outcome_observe", task, conflict).get("error") == "conflict", "historical conflict admitted")
    require(api.outcome("outcome_observe", task, dict(recovery, predecessor=None)).get("error") == "stale_predecessor",
            "stale recovery admitted")
    baseline = snapshot(api.base, task)
    require(api.native("kanban_show", task_id=task, board="outcome-test")["comments"] == original["comments"],
            "retry or rejection appended")
    result = api.outcome("outcome_observe", task, recovery)
    require(result["ok"] and result["view"]["state"] == "confirmed", "post-new-delivery recovery failed")
    require(len(result["view"]["observations"]) == 3, "recovery replaced history")
    require(preserved(baseline, snapshot(api.base, task), 1), "recovery changed native lifecycle")
    after = api.native("kanban_show", task_id=task, board="outcome-test")["comments"]
    require(after[:-1] == original["comments"], "original bytes or provenance changed")
    reread = api.reopen(task, "show", "outcome-test-recompletion-reader")
    require(reread["view"] == result["view"] and reread["comments"] == after,
            "fresh registered reader lost recompletion history")
    return {"native_recompletion_recovery_preserves_history": True}


def failure_cases(api):
    disabled = api.create()
    require(api.reopen(disabled, "disabled", "outcome-test-disabled", enabled=False)["completed"], "disabled path failed")
    malformed = api.create()
    api.native("kanban_comment", task_id=malformed, board="outcome-test", body="[hermes-outcome:v1]\n{")
    require(api.outcome("outcome_show", malformed)["view"]["state"] == "invalid_history", "malformed metadata hidden")
    ordinary_delivery(api, malformed)
    callback = api.create()
    require("error" in api.call("native_test_raise", {}, allow_error=True), "raised callback did not reach real registry")
    ordinary_delivery(api, callback)
    for mode, expected, additions in (("read_error", "native_failure", 0),
                                     ("write_error", "write_unverified", 1),
                                     ("readback_error", "write_unverified", 1)):
        task = api.create()
        baseline = snapshot(api.base, task)
        api.call("native_test_control", {"mode": mode})
        failed = api.outcome("outcome_define", task, api.payload("contract", task))
        require(failed["error"] == expected, "fault did not exercise expected boundary")
        calls = api.call("native_test_control", {"mode": "normal"})["calls"]
        require(calls.count("kanban_comment") == additions, "fault auto-retried native write")
        require(preserved(baseline, snapshot(api.base, task), additions), "fault changed native history")
        ordinary_delivery(api, task)
    sensitive = api.create()
    api.complete(sensitive)
    baseline = snapshot(api.base, sensitive)
    payload = api.payload("contract", sensitive)
    payload["notes"] = "password: synthetic-only-not-a-secret"
    refused = api.outcome("outcome_define", sensitive, payload)
    require(refused["error"] == "sensitive_input", "sensitive evidence admitted")
    payload["notes"] = "x" * 65536
    require(not api.outcome("outcome_define", sensitive, payload)["ok"], "oversize admitted")
    require(preserved(baseline, snapshot(api.base, sensitive), 0), "admission rejection wrote native records")
    token = "sk-" + "SYNTHETIC_NOT_A_SECRET_1234567890"
    api.native("kanban_comment", task_id=sensitive, board="outcome-test", body=json.dumps({"synthetic": token}))
    stored = api.native("kanban_show", task_id=sensitive, board="outcome-test")["comments"][-1]["body"]
    # The pinned public writer uses a six-character head/four-character tail
    # display mask, not a REDACTED sentinel. Assert the actual stored JSON value.
    require(token not in stored and json.loads(stored)["synthetic"] == token[:6] + "..." + token[-4:],
            "native synthetic redaction not exercised")
    require(preserved(baseline, snapshot(api.base, sensitive), 1), "native redaction changed completion")
    return {"disabled_malformed_raised_isolation": True, "read_write_readback_failures": True,
            "sensitive_size_stored_readback": True}


def parallel_observations(api, task, payloads, index):
    profiles = [f"outcome-test-race-{index}-{suffix}" for suffix in ("a", "b")]
    release = api.base / "release"
    release.unlink(missing_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(api.reopen, task, "race", profile, payload)
                   for profile, payload in zip(profiles, payloads)]
        try:
            deadline = time.monotonic() + 25
            while not all((api.base / ("ready-" + profile)).exists() for profile in profiles):
                require(time.monotonic() < deadline, "native race failed to share pre-write snapshot")
                time.sleep(0.01)
        finally:
            release.touch()  # Release even on failure, never orphan barrier children.
        replies = [future.result() for future in futures]
    require(all(reply.get("may_have_persisted") for reply in replies), "race did not attempt both appends")
    return profiles


def race_cases(api):
    for index, mode in enumerate(("identical", "conflicting", "fork")):
        task = api.create()
        require(api.outcome("outcome_define", task, api.payload("contract", task))["ok"], "race definition failed")
        api.complete(task)
        baseline = snapshot(api.base, task)
        first = api.payload("confirmed", task)
        second = copy.deepcopy(first)
        if mode == "conflicting":
            second["summary"] = "Conflicting retry claim"
        if mode == "fork":
            second["record_id"] = "oo_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        profiles = parallel_observations(api, task, [first, second], index)
        view = api.outcome("outcome_show", task)["view"]
        require(preserved(baseline, snapshot(api.base, task), 2), "race changed native completion or runs")
        if mode == "identical":
            occurrences = view["observations"][-1]["provenance"]["samples"]
            require(view["state"] == "confirmed" and len(occurrences) == 2, "identical race lost logical retry/provenance")
            require({row["author"] for row in occurrences} == set(profiles), "race lost native authors")
        else:
            expected = "conflicting_payload" if mode == "conflicting" else "fork"
            require(expected in view["diagnostics"] and view["latest"] is None, "race chose an invented winner")
            require(view["state"] == "invalid_history", "race ambiguity hidden")
    return {"parallel_same_id_retries_conflicts_forks": True}
