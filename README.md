# Hermes Outcome Loop

**Status: Phase-0 feasibility evidence awaiting independent review. No outcome plugin is implemented or installed yet.**

A small native-Hermes extension for **objective → delivery → observed outcome**.
Native Hermes Kanban remains the sole execution authority. Outcome contracts and
observations will be append-only structured comments on a durable delivery root;
there is no independent outcome database or scheduler.

## Project documents

- [Original project handoff](docs/project-handoff.md)
- [Reviewed MVP constraints](docs/mvp-constraints.md) — governs clarifications to the handoff
- [Delivery roadmap](docs/roadmap.md)
- [Phase-0 findings and reproduction](docs/phase-0-findings.md) — current real-runtime results and preserved original NO-GO evidence
- [Approved logical-ordering amendment](docs/decisions/2026-10-01-record-ordering.md) — logical predecessor reconstruction, not timestamp ordering
- [Contributor and agent boundaries](AGENTS.md)

The proposed tool surface is `outcome_define`, `outcome_show`, `outcome_observe`,
and `outcome_check`. These are planned interfaces, not currently available tools.
Installation instructions and exercised examples will be added after implementation.

## Verification

```sh
python3 scripts/verify.py
```

The verifier checks the documents, harness safety regressions and a mandatory
registered-plugin/disposable-board feasibility probe. Set `HERMES_PHASE0_SOURCE`
to the read-only installed Hermes checkout and `HERMES_PHASE0_PYTHON` to its already
provisioned dependency venv's `bin/python` (preserve the symlink). Missing runtime
prerequisites fail, never skip. See the findings for exact reproduction commands.

The resumed suite exercises logical predecessor reconstruction, real registered
plugin dispatch in headless and dispatcher-spawned CLI worker contexts, native
task/board fences, cross-profile restart and concurrent appends, observer
error/slow/disabled behavior, stored redaction and bounded history scaling.
It passes on the recorded installed runtime; independent exact-artifact review
is still required. The fixture is not a production outcome plugin or approved
schema. Future work must extend this same command for schemas, architecture,
packaging and integration. Official-doc receipts can be refreshed explicitly with
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
