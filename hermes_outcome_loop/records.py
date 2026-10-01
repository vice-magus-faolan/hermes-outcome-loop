# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict v1 codec. Only fixed distribution schemas are read, never evidence.

Validation and encoding have no side effects. Checksums detect corruption, not
identity or authenticity. Admission is bounded, not a universal secret detector.
"""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

MARKER = "[hermes-outcome:v1]\n"
MAX_RECORD_BYTES = 16384
MAX_COMMENTS = 1024
MAX_HISTORY_BYTES = 2097152
SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas"


class OutcomeError(ValueError):
    """Safe diagnostic code only; never include a rejected value or native error."""


def timestamp(value: object) -> datetime:
    """Parse calendar-valid UTC to seconds without normalization."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise OutcomeError("invalid_timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise OutcomeError("invalid_timestamp") from None


def offline(uri: str):
    """Unknown schema references fail; network retrieval is never enabled."""
    raise NoSuchResource(ref=uri)


def load_validators() -> tuple[dict, dict]:
    values = [json.loads((SCHEMA_ROOT / f"{name}.schema.json").read_text(encoding="utf-8"))
              for name in ("common", "contract", "observation")]
    for value in values:
        Draft202012Validator.check_schema(value)
    registry = Registry(retrieve=offline).with_resources(
        (value["$id"], Resource.from_contents(value)) for value in values)
    checker = FormatChecker()

    @checker.checks("date-time", raises=ValueError)
    def valid_time(value):
        if isinstance(value, str):
            timestamp(value)
        return True

    validators = {name: Draft202012Validator(value, registry=registry, format_checker=checker)
                  for name, value in zip(("contract", "observation"), values[1:])}
    return validators, values[0]


VALIDATORS, COMMON_SCHEMA = load_validators()
POINTER_PATTERN = COMMON_SCHEMA["$defs"]["pointer"]["pattern"]
SENSITIVE = re.compile(r"(?:\b(?:[a-z_]*api[_-]?key|[a-z_]*token|password|secret)\s*[:=]|\bbearer\s|-----BEGIN .*PRIVATE KEY-----|\[REDACTED\]|\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+)", re.IGNORECASE)
URI = re.compile(r"(?<![A-Za-z0-9+._-])[A-Za-z][A-Za-z0-9+.-]*:[^\s]+")


def utf8_length(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeError:
        return None


def admit_text(value: str) -> None:
    if utf8_length(value) is None:
        raise OutcomeError("malformed_record")
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
        raise OutcomeError("control_character")
    if SENSITIVE.search(value):
        raise OutcomeError("sensitive_input")
    for token in URI.findall(value):
        try:
            parsed = urlsplit(token)
        except ValueError:
            raise OutcomeError("unsafe_pointer") from None
        if parsed.scheme != "https" or parsed.username or parsed.query or parsed.fragment:
            raise OutcomeError("unsafe_pointer")
        if not re.fullmatch(POINTER_PATTERN, token):
            raise OutcomeError("unsafe_pointer")


def admit_values(value: object, depth: int = 0) -> None:
    """Bound recursion and reject non-JSON values before schema traversal."""
    if depth > 12:
        raise OutcomeError("nesting_limit")
    if isinstance(value, str):
        admit_text(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise OutcomeError("malformed_record")
            admit_text(key)
            admit_values(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            admit_values(child, depth + 1)
    elif value is not None and type(value) not in (int, bool):
        raise OutcomeError("noninteger_number")


def payload_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def seal(value: dict) -> dict:
    """Derive checksum in a copy; caller identity and semantic fields stay literal."""
    if not isinstance(value, dict):
        raise OutcomeError("malformed_record")
    admit_values(value)
    result = copy.deepcopy(value)
    result.pop("payload_sha256", None)
    result["payload_sha256"] = hashlib.sha256(payload_json(result).encode("utf-8")).hexdigest()
    return result


def validate(value: object) -> None:
    admit_values(value)
    if not isinstance(value, dict) or value.get("type") not in VALIDATORS:
        raise OutcomeError("malformed_record")
    if type(value.get("version")) is not int or value["version"] != 1:
        raise OutcomeError("unsupported_version")
    if not VALIDATORS[value["type"]].is_valid(value):
        raise OutcomeError("malformed_record")
    if seal(value)["payload_sha256"] != value["payload_sha256"]:
        raise OutcomeError("integrity_mismatch")
    if value["type"] == "contract":
        ids = [criterion["id"] for criterion in value["criteria"]]
        if len(set(ids)) != len(ids):
            raise OutcomeError("malformed_record")


def canonical(value: dict) -> str:
    return MARKER + payload_json(value)


def encode(value: dict) -> str:
    validate(value)
    body = canonical(value)
    if len(body.encode("utf-8")) > MAX_RECORD_BYTES:
        raise OutcomeError("record_limit")
    return body


def unique_pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise OutcomeError("malformed_record")
        result[key] = value
    return result


def reject_constant(value: str):
    raise OutcomeError("malformed_record")


def decode(body: object) -> dict:
    size = utf8_length(body)
    if size is None or not isinstance(body, str):
        raise OutcomeError("malformed_record")
    if not body.startswith(MARKER):
        raise OutcomeError("unsupported_version")
    if size > MAX_RECORD_BYTES:
        raise OutcomeError("record_limit")
    try:
        value = json.loads(body[len(MARKER):], object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        validate(value)
    except OutcomeError:
        raise
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise OutcomeError("malformed_record") from None
    return value
