# Core implementation and unit acceptance

The source package `hermes_outcome_loop` implements the four explicit tools. It is
not installed into any live Hermes profile. Production real-native integration,
plugin packaging/dependency admission, independent exact-artifact review and
repository delivery are separate gates; the Phase-0 probe is feasibility evidence.

## Boundaries and entry point

- `hermes_outcome_loop.register(ctx)` uses only the public `ctx.register_tool` API.
  Handlers return JSON strings, use toolset `outcome`, never override native tools,
  and register no hooks. Dispatcher metadata is not accepted as caller authority.
- `records.py` implements closed schema validation, recursive admission, canonical
  UTF-8 encoding, checksum derivation and decoding. Fixed distribution schemas are
  loaded once from the adjacent `schemas/` directory. There is no remote schema
  resolution, evidence URL fetch or arbitrary file read.
- `history.py` is a pure bounded reconstruction layer. Native source bodies,
  authors and times survive each admitted occurrence; unknown native metadata is
  ignored, not executed or copied. All conflicting variants survive, while union
  graph errors and contract/evidence diagnostics never choose a representative.
- `adapter.py` has one public native dispatch site with a runtime allowlist and
  literal `kanban_show`/`kanban_comment` callers. No database, private native import,
  native CLI fallback, lifecycle operation, durable lock or per-profile outcome state.
  Only actual native comments are parsed, never duplicated `worker_context` prose.

The adapter's transport, environment and clock injection points are host/test APIs,
not exposed tool arguments. Production registration uses the actual environment and
UTC clock. Even empty worker task/run/DB pin variables require a verifiable board
slug. Board fences are rechecked at every dispatch without changing environment
pins. Native task identity and status shape are checked before presenting a view;
status must be a bounded lowercase identifier, and only literal `done` permits
observations. Known `task.completed_at` supplies the native completion anchor.
Unknown completion time stays unknown; recent events are not an inferred anchor.

Runtime dependencies are pinned in `requirements.txt` and exercised via the
repo-local development environment. Reusing reviewed JSON schemas through
`jsonschema`/`referencing` avoids a second handwritten shape contract. Shipping the
fixed schemas and admitting these dependencies through supported Hermes packaging
are mandatory downstream work, not an instruction to install into a live profile.

## Tool inputs and outputs

The signatures and full payload fields are specified by
[record protocol v1](record-protocol.md). Caller payloads omit `payload_sha256`;
the adapter derives it. All semantic fields, including IDs, nulls, predecessor,
observation time and criterion order, remain literal. Public tool schemas are
closed and inline their fixed local definitions; they contain no external `$ref`.
A board argument can be omitted only by a verifiably pinned worker. Headless calls
need an explicit board even when an ambient board variable exists.

`outcome_show` and `outcome_check` issue exactly one fresh native show, with no
append. A read result has `ok: true` and `view`; this means the read was performed,
not that an outcome is successful. Inspect `view.state`, `diagnostics`, `action`
and nullable `head`. Invalid history has `HISTORY_ATTENTION` and no selected head.
Views contain the resolved target/native delivery facts, immutable contract,
causal chain/history, all variants and native occurrences, latest criterion
evidence/residual risk, timing and text-only action/suggestion.

`outcome_check` accepts explicit integration/deployment/first-workflow UTC anchors.
They are caller-supplied evidence, not persisted truth. Callers resupply them after
restart. A done anchor comes only from native completion, never from a caller
`done` field. Awaiting-observation timing distinguishes unknown, not due, exactly
due and overdue using the earliest supported bound. Observed cards have
`not_applicable` due status: an old deadline cannot invent a repeat cadence.
Calendar range is checked before delay addition. A derived instant beyond year
9999 adds nonfatal `timing_diagnostics: ["derived_due_out_of_range"]`; an earlier
absolute deadline still determines timing. Without another bound, `not_due` with
null `due_at` explicitly means the known instant is outside the supported UTC
range, not that its anchor is unknown. No clamped/invented timestamp, invalid
history or predictable post-append read failure is introduced. These admitted
contracts may be defined and retried normally. See the protocol for exact output.

Define/observe first admit locally, then read and reconstruct. An identical valid
retry returns `acknowledgment: identical_retry` with no append; observe retries
still require current native done. A new write preflights the proposed full-history
limits and contextual invariants, attempts at most one native comment, then reads
again. `acknowledgment: verified` requires exact stored bytes, native provenance,
matching payload and admissible entire fresh history. There is no physical
exactly-once or atomic status/uniqueness promise.

Safe operation failures return `ok: false`, an error code, diagnostics and
`may_have_persisted`. Rejected payloads and native exception strings are never
returned. Useful admission codes include `invalid_arguments`, `board_required`,
`board_fence`, `target_mismatch`, `malformed_record`, `unsupported_version`,
`record_limit`, `history_limit`, `unfinished_task`, `pre_delivery_observation`,
`unknown_contract`, `conflict`, `stale_predecessor` and `invalid_history`. Native
read failures are `native_failure` or `malformed_native_response`; unexpected host
failures become `operation_failure`. Malformed outcome history remains visible
via a fresh show's diagnostic codes from the protocol.

After an attempted append, tool error/exception/timeout, missing/changed/redacted
stored content, invalid provenance/history, fork/conflict or changed native target/
status/board yields `write_unverified` and `may_have_persisted: true`. This is not a
persisted assessment. No rollback, fallback or automatic retry occurs. If dispatch
may have been attempted, uncertainty is conservative. A later explicit identical
retry can deduplicate valid persisted data. A damaged marked record can permanently
invalidate a history; MVP has no automatic repair or reconciliation operation.
Native dispatch is synchronous and has no proven cancellable hard timeout.

## Executed coverage

[Production test mapping](../tests/fixtures/outcome/production-map.json) names
executable unit/architecture gates for every ADR boundary. Canonical verification
fails if a mapped gate disappears from discovery. It also retains closed schema
checks, the specification oracle, mandatory real-runtime Phase-0 checks and
conservative complexity auditing of production source.

- `test_outcome_core.py`: approved golden/negative/URI/native/history fixtures;
  all history permutations; tied times; checksum/canonical UTF-8; limits; variant/
  occurrence preservation; all five assessments, regression/recovery, baselines
  and known delivery time.
- `test_outcome_adapter.py`: public registration; all four operations; no-write
  reads; retry/conflict/stale head; every unfinished status including old retries;
  evidence/artifact/author admission; headless/worker board fences; initial read
  failures; append/readback exceptions and timeout; redaction and missing content;
  post-write fork/conflict/lifecycle/target/board changes; pre-append history caps;
  truthful anchors and follow-up/NO_ACTION_REQUIRED.
- `test_outcome_boundaries.py`: simultaneous fake-transport preflight/appends for
  identical retries, both definition-conflict forms and observation forks/conflicts;
  late-race snapshots; noncanonical-but-semantically-equal stored readback; malformed
  native statuses; empty worker pins; unknown data-only native metadata; native
  completion/due boundary checks; inline schemas and static/dynamic allowlists.
- `test_outcome_verification.py`: every named production gate must be discovered;
  removing any required gate fails closed.
- `test_outcome_timing.py`: review regressions for an overflowing external anchor
  with an earlier deadline and native done-anchor define/readback/retry/fresh reads;
  all four anchors at the last representable second, zero/maximum delays, explicit
  upper-bound deadlines, four-digit low years and unknown/nonapplicable controls;
  an observation still appends/verifies and confirmed remains NO_ACTION_REQUIRED.
  The specification oracle independently compares elapsed durations, avoiding
  the same overflow without sharing production timing helpers.

The fake transport is deliberately named and never represented as a native result.
No outcome test reads the live board. Real production registration, native review/
run/event preservation, restart/multi-profile behavior, disabled-plugin isolation
and dependency packaging must be exercised by their downstream lanes. No remote
CI, publication, installation or pilot success is claimed here.

RED/GREEN evidence includes the initial missing implementation imports, then
specific malformed-native-status and empty-worker-pin tests that accepted unsafe
reads before their fixes and pass afterward. A control-character regression also
rejects DEL/C1 in addition to C0, as required by the protocol's control prohibition.
The production codec is exercised
against the reviewed fixtures independently of the oracle module; it does not
import or call that oracle.

Timing remediation RED/GREEN: new tests against the prior adapter reproduce both
review findings (`operation_failure` hiding an earlier deadline and
`write_unverified` after a predictable native-done-anchor append). Range checks
restore readable define/readback/retry/show/check, preserving native provenance
and outcome state while reporting the range limitation separately. Upper-bound,
zero-delay and earlier-deadline controls are required production timing gates.

Complexity soft warnings remain on timing presentation, preflight, union topology/evidence/context
aggregation, presentation and recursive admission. These small boundary functions
aggregate all errors or derive a complete view rather than silently short-circuit
conflicting variants. Permutation, negative, race and limit tests justify the
branching; no production function exceeds the hard threshold of 15. The conservative
score counts comprehensions and boolean conditions, not just control-flow branches.
Timing presentation scores 11: it keeps missing, known, out-of-range and
nonapplicable timing distinct, with full-range and no-write controls; the actual
range-checked addition is isolated in a small helper.

## Residual risks

Python plugins are not sandboxed. Architecture tests constrain this implementation,
not malicious replacements. Admission cannot prove arbitrary encoded/opaque secrets
absent; native redaction can permanently invalidate persisted records. Checksums
are corruption detection, not authentication. Evidence completeness is not evidence
truth. Native full-thread materialization occurs before application caps and is not
an allocation bound. Read/append/read is not atomic; later races can invalidate
later views. Nonterminating native dispatch can delay the caller. These constraints
remain explicit; none is hidden by a lock, scheduler, evidence crawler or second
source of authority.
