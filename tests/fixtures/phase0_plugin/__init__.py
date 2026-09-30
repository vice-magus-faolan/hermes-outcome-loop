# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable feasibility fixture, NOT the outcome plugin.

Setup/completion tools are permitted only in this test fixture. The eventual
outcome adapter remains restricted to kanban_show and kanban_comment.
"""
import json

ALLOWED = {"kanban_create", "kanban_complete", "kanban_show", "kanban_comment"}


def register(ctx):
    """Register a real dispatch probe and post-commit observer."""
    observations = []

    def dispatch(params, **kwargs):
        del kwargs
        operation = params["operation"]
        if operation == "observations":
            return json.dumps({"observations": observations})
        if operation not in ALLOWED:
            return json.dumps({"error": "operation outside fixture allowlist"})
        return ctx.dispatch_tool(operation, params["arguments"])

    ctx.register_tool(
        name="phase0_dispatch",
        toolset="phase0_probe",
        schema={
            "name": "phase0_dispatch",
            "description": "Disposable native interface feasibility probe",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["operation", "arguments"],
            },
        },
        handler=dispatch,
    )

    def completed(task_id, board, **kwargs):
        del kwargs
        state = json.loads(ctx.dispatch_tool(
            "kanban_show", {"task_id": task_id, "board": board}))
        observations.append({
            "status": state["task"]["status"],
            "has_completed_event": any(
                event["kind"] == "completed" for event in state["events"]),
            "has_completed_run": any(
                run["outcome"] == "completed" for run in state["runs"]),
            "profile": ctx.profile_name,
            "mode": "normal",
        })

    ctx.register_hook("kanban_task_completed", completed)
