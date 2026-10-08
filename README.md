# Hermes Outcome Loop

**Status: Phase-0, ADR/schemas and four-tool core independently reviewed. Docker integration source prepared, but native construction/acceptance and packaging remain blocked. No live installation.**

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
- [Docker integration source handoff](docs/docker-integration.md) — exercised runner mechanics, unknown construction budget and unexercised native gates
- [Contributor and agent boundaries](AGENTS.md)

The source package implements `outcome_define`, `outcome_show`, `outcome_observe`,
and `outcome_check` through `hermes_outcome_loop.register(ctx)`. They are not
installed into live profiles. Production-native exercised examples and supported
installation instructions belong to the downstream integration/packaging gates.

## Verification

Canonical verification requires a separately provisioned, budget-admitted Docker
image. Image construction is currently blocked by unknown peaks; do not restart
the interrupted host preparer. See the Docker handoff before any provisioning.

```sh
export HERMES_OUTCOME_IMAGE="$(docker image inspect outcome-integration:local --format '{{.Id}}')"
python3 scripts/verify.py
```

The verifier checks the documents, closed JSON schemas/golden/negative/contextual
fixtures, production unit/architecture tests and required acceptance-map discovery,
harness safety regressions, the mandatory registered-plugin/disposable-board
feasibility probe and new production-native integration gates. The restricted
runner supplies pinned container-only `HERMES_PHASE0_SOURCE` and
`HERMES_PHASE0_PYTHON`; it does not mount installed host Hermes. Missing images or
runtime prerequisites fail, never skip. The new native cases are authored but
unexercised; current canonical acceptance is not green.

The resumed suite exercises logical predecessor reconstruction, real registered
plugin dispatch in headless and dispatcher-spawned CLI worker contexts, native
task/board fences, cross-profile restart and concurrent appends, observer
error/slow/disabled behavior, stored redaction and bounded history scaling.
The historical suite passed on the recorded installed runtime and has independent
Phase-0 review. That result does not establish the new Docker environment.
The Phase-0 fixture is not a production outcome plugin or production schema.
The specification oracle has no native dispatch; its checks do not substitute
for production plugin/native acceptance. Core tests exercise the actual source
parser/adapter with an explicit fake transport, not the oracle. Future work must
exercise the new production real-native checks and extend this same command for
supported packaging. Small schema/unit work may use a repo-local venv with
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
