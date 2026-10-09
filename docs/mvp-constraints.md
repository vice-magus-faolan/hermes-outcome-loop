# Reviewed MVP constraints

Approved bootstrap direction: 2026-09-30. These clarifications take precedence
where the original handoff is ambiguous. Phase-0 evidence has independent review.
The [native-record ADR](decisions/2026-10-01-native-record-contract.md),
[v1 record protocol](record-protocol.md) and [acceptance mapping](acceptance-tests.md)
specify independently reviewed implementation decisions. The core implementation
is pending its own exact-artifact review and downstream production-native acceptance.

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
- Reconstruct observations by stable logical record IDs and explicit predecessor
  references persisted in native comments, independent of returned comment order.
  Native comment IDs are not required and timestamps are not ordering authority.
  A unique valid chain has a determinable latest observation; concurrent branches,
  missing predecessors, cycles and same-ID/different-payload conflicts produce
  visible ambiguity/invalid-history diagnostics, never an invented winner.
  Report malformed records, unsupported versions and orphan observations.
  Preserve each native author/time occurrence when grouping identical retries;
  do not silently collapse contradictory provenance. Do not label unreadable or
  ambiguous history `untracked` or claim an unqualified successful outcome.
  See the [approved ordering amendment](decisions/2026-10-01-record-ordering.md).
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
- Timing arithmetic must remain readable across the full admitted UTC calendar
  and delay ranges. An anchor+delay beyond year 9999 is reported separately as
  `derived_due_out_of_range`, never clamped or treated as invalid history. Any
  absolute deadline wins over that later bound; without one the outcome is not
  yet due for any supported clock, with null due timestamp and an explicit range
  message. Missing anchors remain distinct from known out-of-range derived bounds.
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
or extra task database. Omit the completion hook: Phase 0 found incorrect cross-board
routing and synchronous caller delay; correctness derives from explicit fresh reads.
The four proposed tools are sufficient. Follow-up work is suggested, never created.

## Phase-0 stop rule

Prove all required public interfaces using an isolated real Hermes environment.
If a prerequisite fails, document the smallest design adjustment and block native
review/completion until the feasibility requirement is satisfied or the operator
explicitly accepts a revised scope. Do not bypass the API boundary or alter Hermes
source/configuration merely to make this plugin feasible.

## Current integration recovery

The [Docker recovery decision](decisions/2026-10-08-docker-test-recovery.md)
supersedes active host-side native test preparation. Native feasibility,
integration and downstream packaging run in disposable restricted Docker,
with separate public-only provisioning and ordinary finite-deadline builds.
The continuation authorizes local construction without measured-peak approval;
check actual backing-mount space and retain a 2 GiB operational reserve, not a
claimed quota or fit guarantee. Unknown peaks remain unknown. Preserve failed
attempts/partial preparation; do not mount or reconstruct them. See the
[integration report](docker-integration.md) for actual results and native
assertions. No prior evidence is rewritten into a pass.
