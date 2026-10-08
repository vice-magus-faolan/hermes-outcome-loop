# SPDX-License-Identifier: GPL-3.0-or-later
"""Load unmodified production source with a real public PluginContext.

Only this test loader adds fault injection and a non-authoritative race barrier.
Normal dispatch forwards to the real ctx method, never fake native handlers.
"""
import json
import os
from pathlib import Path
import time


def register(ctx):
    from .hermes_outcome_loop import register as production_register

    original = ctx.dispatch_tool
    fault = {"mode": None, "calls": []}

    def dispatch(name, arguments):
        fault["calls"].append(name)
        mode = fault["mode"]
        if mode == "read_error" and name == "kanban_show":
            raise RuntimeError("synthetic private dispatch error")
        result = original(name, arguments)
        if mode == "write_error" and name == "kanban_comment":
            raise TimeoutError("synthetic private uncertain write")
        if mode == "readback_error" and name == "kanban_comment":
            fault["mode"] = "read_error"
        if mode == "race" and name == "kanban_show":
            fault["mode"] = None
            root = Path(os.environ["HOME"]).parent.resolve(strict=True)
            (root / ("ready-" + os.environ["HERMES_PROFILE"])).touch()
            deadline = time.monotonic() + 15
            while not (root / "release").exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("test-only race barrier timeout")
                time.sleep(0.01)
        return result

    ctx.dispatch_tool = dispatch
    production_register(ctx)

    def control(params, **kwargs):
        del kwargs
        fault["mode"] = params.get("mode")
        previous = list(fault["calls"])
        fault["calls"].clear()
        return json.dumps({"calls": previous})

    ctx.register_tool(name="native_test_control", toolset="native_test",
                      schema={"name": "native_test_control", "description": "Disposable fault control",
                              "parameters": {"type": "object", "properties": {"mode": {"type": "string"}}}},
                      handler=control)

    def native_dispatch(params, **kwargs):
        del kwargs
        return original(params["operation"], params["arguments"])

    def raised_handler(params, **kwargs):
        del params, kwargs
        raise RuntimeError("synthetic integration callback failure")

    for name, handler in (("native_test_dispatch", native_dispatch), ("native_test_raise", raised_handler)):
        ctx.register_tool(name=name, toolset="native_test",
                          schema={"name": name, "description": "Disposable native test operation",
                                  "parameters": {"type": "object", "properties": {
                                      "operation": {"type": "string"}, "arguments": {"type": "object"}}}},
                          handler=handler)
