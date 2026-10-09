# Hermes Outcome Loop

**Status: Phase-0, ADR/schemas, four-tool core and Docker native integration independently reviewed. Directory packaging is implemented and under verification/review. No live installation or publication.**

A small native-Hermes extension for **objective → delivery → observed outcome**.
Native Hermes Kanban remains the sole execution authority. Outcome contracts and
observations are append-only structured comments on a durable delivery root;
there is no independent outcome database or scheduler.

## Project documents

- [Original project handoff](docs/project-handoff.md)
- [Reviewed MVP constraints](docs/mvp-constraints.md) — governs clarifications to the handoff
- [Delivery roadmap](docs/roadmap.md)
- [Phase-0 findings and reproduction](docs/phase-0-findings.md) — current real-runtime results and preserved original NO-GO evidence
- [Approved logical-ordering amendment](docs/decisions/2026-10-01-record-ordering.md) — logical predecessor reconstruction, not timestamp ordering
- [Native-record ADR](docs/decisions/2026-10-01-native-record-contract.md), [record protocol](docs/record-protocol.md) and [acceptance-to-test map](docs/acceptance-tests.md) — reviewed implementation contract
- [Core implementation](docs/core-implementation.md) — source interfaces, unit/architecture coverage, safe errors and downstream gates
- [Docker integration report](docs/docker-integration.md) — pinned build, restricted execution and actual native results
- [Packaging and installation](docs/packaging.md) — reproducible directory artifact, supported admission, rollback and compatibility
- [Authority threat/failure model](docs/threat-model.md) — allowed operations, non-sandbox limits and uncertain writes
- [Contributor and agent boundaries](AGENTS.md)

The source package implements `outcome_define`, `outcome_show`, `outcome_observe`,
and `outcome_check` through `hermes_outcome_loop.register(ctx)`. They are not
installed into live profiles. Build a portable directory/tarball with
`python3 scripts/package_plugin.py --output dist` (stdlib only). Tests and Docker
are repository verification inputs, not shipped plugin runtime components.

## Exercised workflow

These calls are the synthetic scenario executed by the real installed-plugin
packaging test, not evidence that a real deployed workflow improved. Use an
existing durable root and an explicit board. Full payload shapes and required
evidence fields are in the [record protocol](docs/record-protocol.md); repository
golden inputs are in `tests/fixtures/outcome/golden.json` (omit `payload_sha256`
when submitting, replace board/task and supply truthful observation time/evidence).

1. `outcome_define(board=BOARD, task_id=ROOT, contract=contract)` returns `planned`.
   Retain the complete payload and stable `oc_…` ID. The contract maps a real
   workflow criterion to expected post-delivery behavior and descriptive timing.
2. Native review/completion marks the root `done`; it does not confirm the outcome.
   `outcome_check(board=BOARD, task_id=ROOT)` returns `awaiting_observation`;
   deployment-relative timing has no due timestamp until a real anchor is known.
3. `outcome_observe(board=BOARD, task_id=ROOT, observation=confirmed)` appends the
   first `oo_…` record with `predecessor: null`, criterion-mapped outcome evidence,
   environment/artifact and residual risk. Exact stored-body readback returns
   `confirmed`; `outcome_check` returns `NO_ACTION_REQUIRED`.
4. Resubmit the identical complete observation/ID: acknowledgment is
   `identical_retry`, with no additional native comment. A changed payload under
   that ID is not a retry. Concurrent identical writes may still create multiple
   physical comments; logical grouping retains each native occurrence.
5. A later `regressed` observation uses a new ID and names the earlier confirmed
   ID as both `predecessor` and `regression_of`, with before/after comparison.
   Readback is `regressed`; check returns `FOLLOWUP_SUGGESTED`. Delivery stays
   `done`; all prior task/run/event/comment history is preserved. No follow-up is
   created automatically. Fresh processes reconstruct the same view.

Passing builds/tests are delivery verification, not outcome evidence. Unsupported
versions, forks or unreadable history are visible diagnostics, not clean success.
On `write_unverified`, inspect history before any explicit stable-ID retry; no
automatic retry or rollback is promised. See the threat model before persisting
sensitive summaries or evidence pointers. The plugin never fetches evidence.

## Verification

Canonical verification requires a separately provisioned Docker image. Confirm
the actual backing mounts and check the 2 GiB operational reserve before building;
unknown peaks are not a pre-build approval gate. Do not restart the interrupted
host preparer. See the Docker report for provisioning and execution boundaries.

```sh
python3 scripts/docker_build_preflight.py
timeout --signal=TERM --kill-after=30s 1800s docker build --tag outcome-integration:local --file docker/Dockerfile .
export HERMES_OUTCOME_IMAGE="$(docker image inspect outcome-integration:local --format '{{.Id}}')"
python3 scripts/verify.py
```

The verifier checks the documents, closed JSON schemas/golden/negative/contextual
fixtures, production unit/architecture tests and required acceptance-map discovery,
harness safety regressions, the mandatory registered-plugin/disposable-board
feasibility probe, production-native integration and supported distribution
scan/install/PM-admission/registration/removal gates. The restricted
runner supplies pinned container-only `HERMES_PHASE0_SOURCE` and
`HERMES_PHASE0_PYTHON`; it does not mount installed host Hermes. Missing images or
runtime prerequisites fail, never skip. Native integration and original Phase-0
assertions remain mandatory alongside packaging discovery.

The resumed suite exercises logical predecessor reconstruction, real registered
plugin dispatch in headless and dispatcher-spawned CLI worker contexts, native
task/board fences, cross-profile restart and concurrent appends, observer
error/slow/disabled behavior, stored redaction and bounded history scaling.
The historical suite passed on the recorded installed runtime and has independent
Phase-0 review. That result does not establish the new Docker environment.
The Phase-0 fixture is not a production outcome plugin or production schema.
The specification oracle has no native dispatch; its checks do not substitute
for production plugin/native acceptance. Core tests exercise the actual source
parser/adapter with an explicit fake transport, not the oracle. Supported packaging
uses native discovery without the integration loader fixture, including the PM
selected dependency environment. Small schema/unit work may use a repo-local venv with
`requirements-dev.txt`; it is not a host-side Hermes test environment or a
substitute for the canonical native gate.
Official-doc receipts can be refreshed explicitly with
`python3 scripts/phase0_docs.py`; ordinary verification does not fetch evidence.

Important constraints: reject mismatched worker board slugs explicitly, omit the
optional completion hook, and do not treat native redaction as a universal secret
scrubber. See the findings for exercised limitations and required admission/readback
policies. No live installation or publication is authorized by these probes.

## Delivery

Feature work and exact-artifact native review occur on an isolated local lane.
`main` is the integration target. After the initial bootstrap, GitHub delivery is
through pull requests with canonical CI passing; no force-push or direct push to
`main`. Live installation, profile changes, gateway restart and deployment require
separate operator approval. The real-project pilot is approval-gated.

## License

SPDX-License-Identifier: **GPL-3.0-or-later**.
This project is licensed under GNU GPL version 3 or, at your option, any later
version. See [LICENSE](LICENSE).
