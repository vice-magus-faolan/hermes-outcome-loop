# Hermes Outcome Loop

**Status: bootstrap and Phase-0 reconnaissance. No outcome plugin is implemented or installed yet.**

A small native-Hermes extension for **objective → delivery → observed outcome**.
Native Hermes Kanban remains the sole execution authority. Outcome contracts and
observations will be append-only structured comments on a durable delivery root;
there is no independent outcome database or scheduler.

## Project documents

- [Original project handoff](docs/project-handoff.md)
- [Reviewed MVP constraints](docs/mvp-constraints.md) — governs clarifications to the handoff
- [Delivery roadmap](docs/roadmap.md)
- [Phase-0 findings and reproduction](docs/phase-0-findings.md) — current feasibility is NO-GO
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

The current installed public reader omits required native comment IDs, so canonical
verification deliberately fails the feasibility gate. Evidence collection success
is not plugin acceptance. No production plugin has been implemented; remaining
worker/failure/profile probes await a reviewed feasibility decision. Future work
must extend this same command for schemas, architecture, packaging and integration.

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
