# Reviewed MVP constraints

Approved bootstrap direction: 2026-09-30. These clarifications take precedence
where the original handoff is ambiguous. The implementation ADR and schemas
remain pending Phase-0 evidence and independent review.

## Authority and failure

- Only `kanban_show` and `kanban_comment` are allowed through the MVP Kanban
  adapter. No private Kanban imports, direct database access, lifecycle-control
  tools, scheduler, automatic work creation or plugin-owned persistence.
- Python plugins run in-process. Architecture tests and independent review constrain
  this implementation; they are not a sandbox against malicious Python code.
  Exception isolation and disabled-plugin behavior must be tested. Process exit,
  resource exhaustion and hostile plugin code are outside the isolation guarantee.
- Outcome operations must never control completion, review, claims, dependencies,
  dispatcher state or integration. Outcome failure does not reopen delivered work.
- Native comment writes legitimately add `commented` events. Preserve all existing
  delivery events, runs and review provenance; permit only expected native comment
  additions. Do not require an unchanged whole event stream.

## Records and deterministic reconstruction

- MVP uses one immutable contract per delivery root. Repeated identical definitions
  are logically idempotent; conflicting definitions fail visibly.
- Use an explicit version marker and deterministic JSON schema. Contract and
  observation records require stable identifiers. Observation calls need an explicit
  retry key/ID, plus contract identity, so later genuine observations remain distinct.
- Sort by native comment IDs, not timestamp alone. Report malformed records,
  unsupported versions, orphan observations and same-ID/different-payload conflicts.
  Do not silently label an unreadable history `untracked` or claim success from it.
- Concurrent read/append is not an atomic uniqueness operation. The ADR must document
  logical deduplication and conflict reporting using native records, with no hidden
  lock/database becoming authoritative. Race and retry tests are required.
- Native comment author and creation time anchor attribution and persistence time.
  Observation time, environment and delivered artifact (where applicable) are
  explicit data. Caller-provided identities are not trusted as authoritative authors.

## Timing and evidence

- Free-text `observe_when` is descriptive. Only report overdue when a declared
  absolute deadline or a supported externally supplied anchor is known; otherwise
  state `awaiting observation; due time unknown`. No invented deployment timestamp.
- Evidence maps to criteria. Claims of improvement need a baseline/comparison where
  appropriate. Distinguish a verification check from post-delivery outcome evidence.
- Prefer evidence pointers and concise summaries. Never automatically read repository
  files, fetch evidence URLs, collect transcripts or persist credentials.
- Persist through native `kanban_comment` redaction. Reject oversized records rather
  than truncate. Read back and parse the actual stored record before acknowledging
  success; redaction must not break identifiers or silently change contract meaning.
- All operations explicitly resolve board identity and honor native worker board
  restrictions. Cross-profile reads of the same board must reconstruct the same history.

## Scope

No dashboard, scheduler, fleet crawler, automatic remediation, lifecycle interception,
or extra task database. Omit a completion hook unless Phase 0 shows a concrete need;
correctness derives from fresh native reads even if hooks are absent or replayed.
The four proposed tools are sufficient. Follow-up work is suggested, never created.

## Phase-0 stop rule

Prove all required public interfaces using an isolated real Hermes environment.
If a prerequisite fails, document the smallest design adjustment and block native
review/completion until the feasibility requirement is satisfied or the operator
explicitly accepts a revised scope. Do not bypass the API boundary or alter Hermes
source/configuration merely to make this plugin feasible.
