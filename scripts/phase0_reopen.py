# SPDX-License-Identifier: GPL-3.0-or-later
"""Fresh-process public native read/append or disabled-plugin completion probe."""
import json
import os
from pathlib import Path
import sys
import time


def main():
    source, base, task_id, action = sys.argv[1:5]
    root = Path(base).resolve(strict=True)
    for key in ("HOME", "HERMES_HOME", "HERMES_KANBAN_HOME", "TMPDIR"):
        if not Path(os.environ[key]).resolve().is_relative_to(root):
            raise RuntimeError("restart profile path escaped disposable root")
    if any(key in os.environ for key in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_DB", "HERMES_KANBAN_RUN_ID")):
        raise RuntimeError("reopen inherited worker pins")
    sys.path.insert(0, source)
    from hermes_cli.plugins import get_plugin_manager
    from tools.registry import registry
    import tools.kanban_tools  # noqa: F401
    manager = get_plugin_manager()
    manager.discover_and_load()

    def call(operation, arguments):
        if action == "disabled":
            raw = registry.dispatch(operation, arguments, scope=manager.scope_key)
        else:
            raw = registry.dispatch("phase0_dispatch", {"operation": operation, "arguments": arguments},
                                    scope=manager.scope_key)
        if not isinstance(raw, str):
            raise RuntimeError("native registry returned non-string result")
        value = json.loads(raw)
        if "error" in value:
            raise RuntimeError("reopen native operation failed")
        return value

    if action == "disabled":
        if manager.has_hook("kanban_task_completed"):
            raise RuntimeError("plugin observer unexpectedly enabled")
        call("kanban_complete", {"task_id": task_id, "board": "phase0", "summary": "Plugin disabled"})
    race_count = None
    if action == "race":
        initial = call("kanban_show", {"task_id": task_id, "board": "phase0"})
        race_count = len(initial["comments"])
        (root / ("race-ready-" + os.environ["HERMES_PROFILE"])).touch()
        deadline = float(os.environ["OUTCOME_PHASE0_RACE_DEADLINE"])
        while not (root / "race-release").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("disposable race barrier timed out")
            time.sleep(0.01)
    if action in ("append", "race"):
        call("kanban_comment", {"task_id": task_id, "board": "phase0", "body": sys.argv[5]})
    state = call("kanban_show", {"task_id": task_id, "board": "phase0"})
    result = {key: state[key] for key in ("task", "comments", "runs", "events")}
    result["race_read_comments"] = race_count
    print(json.dumps(result))


if __name__ == "__main__":
    main()
