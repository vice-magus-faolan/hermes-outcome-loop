# Hermes Outcome Loop

A native Hermes plugin for **objective → delivery → observed outcome**. Hermes
Kanban owns execution; the plugin records outcome contracts and observations as
append-only comments on an existing task. No extra database, scheduler, dashboard,
or automatic remediation is installed.

## Tools

- `outcome_define(board, task_id, contract)` — declare one immutable expected
  outcome, its criteria, evidence requirements and descriptive observation timing.
- `outcome_show(board, task_id)` — reconstruct the contract and causal observations
  from native comments, retaining attribution and visible history diagnostics.
- `outcome_observe(board, task_id, observation)` — append criterion-mapped evidence
  after the native task is `done`. Retain the complete payload and stable ID for retries.
- `outcome_check(board, task_id, anchors={})` — suggest whether observation or
  follow-up is needed. Missing deployment anchors mean **due time unknown**.

Use an explicit board and an existing durable task. Define the contract before
work, let native Kanban handle delivery/review/completion, then observe the actual
result. A confirmed outcome returns `NO_ACTION_REQUIRED`; a later supported
regression suggests follow-up without reopening the completed task. Passing tests
alone do not prove a post-delivery outcome.

Payloads, retry IDs, predecessors, result/evidence rules and diagnostics are in
[the record protocol](docs/record-protocol.md). Forked or unreadable histories are
reported, never resolved by timestamps. An uncertain append returns
`write_unverified`; inspect history before explicitly retrying the same payload.

## Installation and removal

This is a directory plugin with four tools in toolset `outcome` and no completion
hook. See [packaging and installation](docs/packaging.md) for native install,
dependency consent, enabling the intended profile and safe removal. Read
[the threat model](docs/threat-model.md) before storing evidence. Removing the
plugin does not remove native comments or delivery history.

## Development

Tests use Docker, not another Hermes installation on the host. The pinned image
contains test dependencies; the container loads this checkout read-only. Build
online, then run the production unit, distribution and real-Hermes tests offline:

```sh
docker build -t outcome-loop-test -f docker/Dockerfile .
timeout --signal=TERM --kill-after=10s 300s docker run --rm --init --pull=never \
  --network=none --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --user=65532:65532 --cpus=2 --memory=2g --memory-swap=2g --pids-limit=256 \
  --tmpfs /scratch:rw,exec,nosuid,nodev,size=1g,mode=1777 \
  --mount type=bind,src="$PWD",dst=/source,readonly outcome-loop-test
```

Build a portable directory and deterministic archive with
`python3 scripts/package_plugin.py --output dist` (stdlib only; choose a new output
directory for each build). Test helpers, Docker and development dependencies are
not shipped in the plugin. `AGENTS.md` remains unchanged, including its obsolete
bootstrap statements. Its required original brief and product-reference documents
are retained; this cleanup removes experimental harness and recovery documentation.

## License

**GPL-3.0-or-later**. See [LICENSE](LICENSE).
