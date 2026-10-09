# SPDX-License-Identifier: GPL-3.0-or-later
"""Additional bounded real-runtime probes; no production adapter or schema."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

from phase0_ordering import MARKER, MAX_BYTES, MAX_RECORDS, reconstruct
from phase0_provider import ScriptedProvider
from phase0_snapshot import snapshot, preserved

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def logical(identifier, predecessor=None, summary="evidence"):
    return MARKER + json.dumps({"record_id": identifier, "contract_id": "probe-contract",
                               "predecessor": predecessor, "summary": summary},
                              sort_keys=True, separators=(",", ":"))


def append_records(call, task_id, bodies):
    for body in bodies:
        call("kanban_comment", task_id=task_id, board="phase0", body=body)
    comments = call("kanban_show", task_id=task_id, board="phase0")["comments"]
    require(Counter(item["body"] for item in comments) == Counter(bodies), "native records incomplete")
    return comments


def ordering_probe(call, create):
    bodies = [logical("z"), logical("a", "z"), logical("m", "a"), logical("a", "z")]
    comments = append_records(call, create(), bodies)
    for sequence in (comments, comments[::-1], comments[1:] + comments[:1]):
        result = reconstruct(sequence)
        require(result["latest"] == "m" and not result["diagnostics"], "causal reconstruction failed")
        require(len(result["occurrences"]["a"]) == 2, "retry provenance lost")
    cases = {
        "fork": [logical("z"), logical("a", "z"), logical("m", "z")],
        "conflict": [logical("z"), logical("z", summary="changed")],
        "missing_predecessor": [logical("a", "absent")],
        "cycle": [logical("a", "m"), logical("m", "a")],
        "multiple_roots": [logical("z"), logical("a")],
    }
    for diagnostic, records in cases.items():
        rows = append_records(call, create(), records)
        for sequence in (rows, rows[::-1]):
            result = reconstruct(sequence)
            require(result["latest"] is None and diagnostic in result["diagnostics"], "invented causal winner")
    return {"passed": True, "native_roundtrips": True, "reordered_input": True,
            "identical_retries_preserve_occurrences": True,
            "same_second_ties_observed": len({item["created_at"] for item in comments}) < len(comments),
            "diagnosed": sorted(cases)}


def policy_probe(call, create):
    task = create()
    # Exact UTF-8 total-byte boundary, including marker and serialized metadata.
    base = logical("boundary", summary="x")
    body = logical("boundary", summary="x" * (MAX_BYTES - len(base.encode()) + 1))
    require(len(body.encode()) == MAX_BYTES, "incorrect boundary fixture")
    accepted = call("bounded_append", task_id=task, board="phase0", body=body)
    require(accepted["exact_stored_readback"], "bounded append not verified")
    before = call("kanban_show", task_id=task, board="phase0")
    rejected = call("bounded_append", task_id=task, board="phase0", body=body + "x", allow_error=True)
    require("error" in rejected, "oversized record accepted")
    after = call("kanban_show", task_id=task, board="phase0")
    require(all(after[key] == before[key] for key in ("task", "runs", "events", "comments")),
            "oversized rejection mutated native history")
    changed = call("bounded_append", task_id=task, board="phase0",
                   body=logical("safe", summary="sk-" + "SYNTHETIC_NOT_A_SECRET_1234567890"), allow_error=True)
    require("error" in changed, "redacted mutation acknowledged as exact success")
    return {"passed": True, "experimental_total_byte_cap": MAX_BYTES,
            "exact_boundary_readback": True, "oversized_rejected_before_write": True,
            "redacted_change_not_acknowledged": True, "native_maximum_required": False}


def lifecycle_probe(call, create):
    results = []
    for mode in ("error", "slow", "normal"):
        call("observer_mode", mode=mode)
        task = create(complete=False)
        start = time.perf_counter()
        call("kanban_complete", task_id=task, board="phase0", summary="Observer feasibility")
        elapsed = (time.perf_counter() - start) * 1000
        state = call("kanban_show", task_id=task, board="phase0")
        item = call("observations")["observations"][-1]
        require(state["task"]["status"] == "done" and item["mode"] == mode, "observer completion drift")
        require(item["has_completed_event"] and item["has_completed_run"] and item["later_observer_ran"],
                "observer did not see commit or exception blocked later observers")
        if mode == "slow":
            require(item["parallel_write_finished"], "slow observer held SQLite write lock")
            require(elapsed >= 200, "slow observer was not exercised")
        results.append({"mode": mode, "completion_ms": round(elapsed, 3),
                        "post_commit_visible": True, "later_observer_ran": True,
                        "parallel_write_finished": item.get("parallel_write_finished")})
    return {"passed": True, "callbacks": results, "slow_blocks_caller_not_write_lock": True}


def profile_env(base, profile, enabled=True):
    home = base / "host-home/.hermes/profiles" / profile
    home.mkdir(parents=True, exist_ok=True)
    if enabled and not (home / "plugins/phase0-probe").exists():
        shutil.copytree(ROOT / "tests/fixtures/phase0_plugin", home / "plugins/phase0-probe")
    (home / "config.yaml").write_text("toolsets: [kanban, phase0_probe]\nplugins:\n  enabled: " +
                                    ("[phase0-probe]" if enabled else "[]") + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(HERMES_HOME=str(home), HERMES_PROFILE=profile)
    for key in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_DB", "HERMES_KANBAN_RUN_ID"):
        env.pop(key, None)
    return env


def reopen(source, base, task, action="read", profile="phase0-b", body=None, race_deadline=None):
    args = [sys.executable, "-B", str(ROOT / "scripts/phase0_reopen.py"), str(source), str(base), task, action]
    if body is not None:
        args.append(body)
    env = profile_env(base, profile, action != "disabled")
    if race_deadline is not None:
        env["OUTCOME_PHASE0_RACE_DEADLINE"] = str(race_deadline)
    result = subprocess.run(args, cwd=base, env=env,
                            capture_output=True, text=True, timeout=60 if action == "race" else 30)
    require(result.returncode == 0, "fresh-process public operation failed: " + result.stderr)
    return json.loads(result.stdout)


def profile_probe(call, create, source, base):
    task = create()
    body = logical("profile-retry")
    call("kanban_comment", task_id=task, board="phase0", body=body)
    first = call("kanban_show", task_id=task, board="phase0")["comments"]
    for profile in ("phase0-b", "phase0-a"):
        require(reopen(source, base, task, profile=profile)["comments"] == first, "restart changed native history")
    second = reopen(source, base, task, "append", body=body)["comments"]
    require(len(second) == 2 and {item["author"] for item in second} == {"phase0-a", "phase0-b"},
            "native cross-profile authors missing")
    require(call("kanban_show", task_id=task, board="phase0")["comments"] == second, "profiles diverged")
    grouped = reconstruct(second)
    require(grouped["latest"] == "profile-retry" and len(grouped["occurrences"]["profile-retry"]) == 2,
            "cross-profile retry provenance lost")
    disabled = reopen(source, base, create(complete=False), "disabled", "phase0-disabled")
    require(disabled["task"]["status"] == "done" and any(run["outcome"] == "completed" for run in disabled["runs"]),
            "plugin-disabled completion failed")
    return {"passed": True, "fresh_processes": 4, "profile_authors": ["phase0-a", "phase0-b"],
            "identical_history": True, "retry_provenance": True, "plugin_disabled_completion": True}


def wait_race_readers(base, futures, deadline):
    """Distinguish a failed child from slow imports before releasing real appends."""
    profiles = ("phase0-a", "phase0-b")
    while not all((base / ("race-ready-" + profile)).exists() for profile in profiles):
        for future in futures:
            if future.done():
                future.result()  # Preserve the primary native child error.
                raise RuntimeError("real-profile race child exited before release")
        pending = [profile for profile in profiles if not (base / ("race-ready-" + profile)).exists()]
        require(time.monotonic() < deadline, "real-profile race did not reach read barrier: " + ", ".join(pending))
        time.sleep(0.01)


def race_probe(call, create, source, base):
    """Two real profiles read the same predecessor, then append without a lock."""
    task = create()
    call("kanban_comment", task_id=task, board="phase0", body=logical("z"))
    # One startup+barrier deadline shared with both children; not two independent
    # ten-second clocks. Two native imports compete under the two-CPU ceiling.
    deadline = time.monotonic() + 45
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reopen, source, base, task, "race", profile, logical(identifier, "z"), deadline)
                   for profile, identifier in (("phase0-a", "a"), ("phase0-b", "m"))]
        try:
            wait_race_readers(base, futures, deadline)
        finally:
            (base / "race-release").touch()  # Unblock peers even on primary failure.
        results = [future.result() for future in futures]
    require(all(result["race_read_comments"] == 1 for result in results), "race did not share predecessor snapshot")
    rows = call("kanban_show", task_id=task, board="phase0")["comments"]
    result = reconstruct(rows)
    require(len(rows) == 3 and result["diagnostics"] == ["fork"] and result["latest"] is None,
            "concurrent native fork silently resolved")
    require({item["author"] for item in rows} == {"phase0-a", "phase0-b"}, "race authors missing")
    return {"passed": True, "actual_parallel_profile_appends": True,
            "shared_predecessor_read": True, "fork_visible_no_winner": True}


def cost(call, task):
    elapsed = []
    state = call("kanban_show", task_id=task, board="phase0")
    for _ in range(10):
        start = time.perf_counter()
        state = call("kanban_show", task_id=task, board="phase0")
        result = reconstruct(state["comments"])
        require(not result["diagnostics"], "scaling history unreadable")
        elapsed.append((time.perf_counter() - start) * 1000)
    return {"comments": len(state["comments"]), "samples": len(elapsed),
            "median_ms": round(statistics.median(elapsed), 3), "maximum_ms": round(max(elapsed), 3),
            "response_bytes": len(json.dumps(state).encode())}


def scaling_probe(call, create, base):
    task = create()
    before = snapshot(base, task)
    measurements = []
    previous = None
    count = 0
    for target in (16, 128, 512, MAX_RECORDS):
        while count < target:
            identifier = f"history-{count}"
            call("kanban_comment", task_id=task, board="phase0", body=logical(identifier, previous))
            previous = identifier
            count += 1
        state = call("kanban_show", task_id=task, board="phase0")
        require(len(state["comments"]) == target and reconstruct(state["comments"])["latest"] == previous,
                "native full-history read failed")
        measurements.append(cost(call, task))
    call("kanban_comment", task_id=task, board="phase0", body=logical("overflow", previous))
    require(reconstruct(call("kanban_show", task_id=task, board="phase0")["comments"])["diagnostics"] == ["history_limit"],
            "history limit did not fail visibly")
    require(preserved(before, snapshot(base, task), MAX_RECORDS + 1), "full native delivery history changed")
    return {"passed": True, "full_history_to": MAX_RECORDS, "measurements": measurements,
            "full_native_delivery_history_preserved": True,
            "overflow_visible": True, "interactive_slo_claimed": False}


def worker_config(base, source, url):
    home = Path(os.environ["HERMES_HOME"])
    (home / "config.yaml").write_text(
        "_config_version: 12\nmodel:\n  provider: custom\n  base_url: " + url + "\n  default: phase0-model\n  context_length: 128000\n"
        "agent:\n  api_max_retries: 1\n  max_turns: 4\nupdates:\n  check: false\n"
        "toolsets: [kanban, phase0_probe]\nplatform_toolsets:\n  cli: [kanban, phase0_probe]\n"
        "tools:\n  tool_search:\n    enabled: off\nplugins:\n  enabled: [phase0-probe]\n", encoding="utf-8")
    env = dict(os.environ)
    # Let native dispatch choose the running interpreter's module launcher.
    # Docker's scratch tmpfs is noexec; no executable test shim is necessary.
    env.pop("HERMES_BIN", None)
    env.update(PYTHONPATH=str(source), HERMES_DISABLE_LAZY_INSTALLS="true",
               OPENAI_API_KEY="synthetic-loopback-only", NO_COLOR="1", TERM="dumb")
    return env


def wait_worker(call, task, base):
    deadline = time.monotonic() + 80
    while time.monotonic() < deadline:
        state = call("kanban_show", task_id=task, board="phase0")
        rows = [item for item in state["comments"] if item["body"].startswith("[phase0-worker]\n")]
        if rows:
            return state, rows[0]
        time.sleep(0.1)
    logs = "\n".join(path.read_text(encoding="utf-8", errors="replace")[-5000:]
                     for path in base.rglob("*.log"))
    raise RuntimeError("dispatcher worker failed to produce native evidence: " + logs)


def wait_worker_exit(base):
    """Keep scripted transport alive until the actual detached worker exits."""
    receipt = base / "worker-pids.jsonl"
    require(receipt.is_file(), "public spawn cleanup receipt missing")
    pids = [json.loads(row)["pid"] for row in receipt.read_text().splitlines()]
    require(len(pids) == 1, "unexpected detached worker count")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            stat = Path(f"/proc/{pids[0]}/stat").read_text()
            if stat.rsplit(")", 1)[1].split()[0] == "Z":
                return
        except FileNotFoundError:
            return
        time.sleep(0.05)
    raise RuntimeError("actual worker did not exit after native completion")


def worker_probe(call, create, source, base, sibling, other):
    task = create(complete=False)
    before = call("kanban_show", task_id=sibling, board="phase0")
    native_before = snapshot(base, sibling)
    with ScriptedProvider({"sibling": sibling, "other": other}) as provider:
        env = worker_config(base, source, provider.base_url)
        # Public dispatcher launcher only: never CLI data writes or private mutation APIs.
        result = subprocess.run([sys.executable, "-B", "-m", "hermes_cli.main", "kanban", "--board", "phase0", "dispatch", "--max", "1", "--json"],
                                cwd=base, env=env, capture_output=True, text=True, timeout=40)
        require(result.returncode == 0, "public dispatcher launch failed: " + result.stderr)
        dispatched = json.loads(result.stdout)
        require(any(item["task_id"] == task for item in dispatched["spawned"]),
                "public dispatcher did not spawn probe: " + json.dumps(dispatched) +
                "; native launch error: " + str(call("kanban_show", task_id=task, board="phase0")["task"]["last_failure_error"]))
        state, occurrence = wait_worker(call, task, base)
        report = json.loads(occurrence["body"].split("\n", 1)[1])
        require(report["passed"] and report["profile"] == "phase0-a" and occurrence["author"] == "phase0-a",
                "worker profile or fixture verdict failed")
        require(state["task"]["status"] == "done" and any(run["profile"] == "phase0-a" and run["outcome"] == "completed"
                                                            for run in state["runs"]), "worker completion not canonical")
        require(not any(item["body"] == "must not write" for item in state["comments"]),
                "mismatched board guard mutated worker history")
        require(provider.requests, "actual agent never reached loopback provider")
        wait_worker_exit(base)
    after = call("kanban_show", task_id=sibling, board="phase0")
    require(before["task"] == after["task"] and before["runs"] == after["runs"], "worker altered sibling lifecycle")
    require(len(after["comments"]) == len(before["comments"]) + 1, "worker sibling comment missing")
    require(preserved(native_before, snapshot(base, sibling), 1), "worker changed native sibling delivery history")
    return {**report, "dispatcher_spawned": True, "actual_agent_transport": True,
            "worker_exit_observed": True, "sibling_lifecycle_preserved": True,
            "full_sibling_delivery_history_preserved": True}
