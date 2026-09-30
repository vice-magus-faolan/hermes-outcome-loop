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
- [Contributor and agent boundaries](AGENTS.md)

The proposed tool surface is `outcome_define`, `outcome_show`, `outcome_observe`,
and `outcome_check`. These are planned interfaces, not currently available tools.
Installation instructions and exercised examples will be added after implementation.

## Verification

```sh
python3 scripts/verify.py
```

The initial verifier checks the bootstrap documents and discovers the standard-library
unit test suite. It is not evidence that outcome behavior exists or passes.
Each implementation must extend this same canonical command to cover its new
unit, schema, architecture, packaging and disposable-Hermes integration checks.

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
