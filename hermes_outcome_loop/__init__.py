# SPDX-License-Identifier: GPL-3.0-or-later
"""Public Hermes plugin entry point. Explicit tools only; no hooks or lifecycle interception.

Registration does not call native tools or read profile state. Distribution schemas
are required alongside this source package; packaging is a separate delivery gate.
"""
from __future__ import annotations

import copy
import json

from .adapter import INPUT_FIELDS, OutcomeAdapter
from .records import COMMON_SCHEMA, VALIDATORS

DESCRIPTIONS = {
    "outcome_define": "Define one immutable outcome contract on an existing native delivery root. Retain the caller-chosen record ID for retries; no lifecycle changes.",
    "outcome_show": "Read outcome contract, causal observations, native provenance and visible ambiguity on one board/task. Read only.",
    "outcome_observe": "Append criterion-mapped outcome evidence after native done. Retain complete payload, record ID and predecessor for retries. No automatic follow-up.",
    "outcome_check": "Read outcome attention and truthful due timing for one task. External anchors are caller-supplied evidence; no scheduler or automatic work creation.",
}


def inline_schema(value: object) -> object:
    """Expand only fixed local common definitions into public tool schemas."""
    if isinstance(value, list):
        return [inline_schema(child) for child in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        ref = value["$ref"]
        prefix, name = ref.rsplit("/", 1)
        if prefix not in {"common.schema.json#/$defs", "#/$defs"}:
            raise ValueError("nonlocal_schema_reference")
        return inline_schema(COMMON_SCHEMA["$defs"][name])
    return {key: inline_schema(child) for key, child in value.items() if key not in {"$id", "$schema"}}


def tool_schema(name: str) -> dict:
    properties = {"board": dict(COMMON_SCHEMA["$defs"]["board"], description="Explicit board slug; may be omitted only in a verifiably pinned worker."),
                  "task_id": COMMON_SCHEMA["$defs"]["task_id"]}
    required = ["task_id"]
    field = {"outcome_define": "contract", "outcome_observe": "observation"}.get(name)
    if field:
        payload = copy.deepcopy(VALIDATORS[field].schema)
        payload["properties"].pop("payload_sha256")
        payload["required"].remove("payload_sha256")
        properties[field] = inline_schema(payload)
        required.append(field)
    if name == "outcome_check":
        properties["anchors"] = {"type": "object", "additionalProperties": False,
                                "properties": {key: COMMON_SCHEMA["$defs"]["time"]
                                               for key in ("integration", "deployment", "first_workflow")}}
    return {"name": name, "description": DESCRIPTIONS[name],
            "parameters": {"type": "object", "additionalProperties": False,
                           "properties": properties, "required": required}}


def handler_for(adapter: OutcomeAdapter, name: str):
    """Ignore dispatcher metadata as input authority; use native environment fences."""
    def handler(params, **kwargs):
        del kwargs
        return json.dumps(adapter.invoke(name, params), ensure_ascii=False, allow_nan=False)
    return handler


def register(ctx) -> None:
    """Register exactly four supported public tools, never override native names."""
    adapter = OutcomeAdapter(ctx)
    for name in INPUT_FIELDS:
        ctx.register_tool(name=name, toolset="outcome", schema=tool_schema(name),
                          handler=handler_for(adapter, name), check_fn=lambda: True)
