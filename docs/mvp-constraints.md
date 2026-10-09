# MVP constraints

The [original project brief](project-handoff.md) is retained unchanged. The
[record protocol](record-protocol.md) specifies the implemented MVP and its
clarifications; the plugin runtime and schemas are unchanged by repository cleanup.

- Hermes Kanban is the sole execution authority. The plugin can only read through
  `kanban_show` and append through `kanban_comment`, never control lifecycle or SQL.
- Contracts and observations are native comments only: no second database, durable
  cache, scheduler, dashboard, automatic evidence fetching or automatic work creation.
- Delivery done and outcome confirmed are separate facts. A failed outcome never
  reopens completed delivery or changes its review/run history.
- Logical IDs and explicit predecessors establish causality, not native comment
  IDs, timestamps or list positions. Preserve native attribution; forks, conflicts,
  malformed/unsupported records and unreadable histories are visible diagnostics.
- Admit bounded, criterion-mapped evidence and verify exact persisted readback.
  Uncertain writes may have persisted; never promise rollback or automatically retry.
- Timing is descriptive. Without a supported deadline/anchor, due time is unknown;
  completion does not invent integration/deployment time.
- No completion hook is needed for correctness. Ordinary errors fail observationally;
  Python plugins are not malicious-code sandboxes or hard resource-isolation boundaries.
- Docker runs focused real-Hermes checks and production regression tests. Host
  runtime provisioning, Phase-0 prototypes and package-manager harnesses are not
  plugin deliverables. See README.md for ordinary build/run commands.
- Installation, profile changes, gateway restart and real-project pilot need separate
  operator consent. Human PR approval is distinct from native agent review and CI.
