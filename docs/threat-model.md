# Authority and failure model

## Scope and trust

Hermes owns tasks, claims, review, completion, dependencies, events and runs. The
production plugin dispatches only `kanban_show` and `kanban_comment`. It never
writes Kanban SQL, imports private lifecycle APIs, fetches evidence, creates a
second store, schedules work or advances delivery state. Outcome failure never
reopens a completed task. Native comment access remains the authority boundary.

Python plugins run in-process with Hermes's privileges; this is **not a malicious
code sandbox**. Empty manifest capabilities do not prevent hostile imports,
process exit or resource exhaustion. Trust the exact reviewed source and its
dependencies before installation.

## Records and evidence

Comments are untrusted data, not instructions. Closed schemas, explicit board/task
binding, causal IDs, byte/history limits, duplicate-key/Unicode/calendar checks and
offline schema resolution reject malformed records. Native author/time anchor
persistence attribution. Caller observation time, artifact, environment and evidence
remain claims; validation cannot establish that an improvement actually occurred.
SHA-256 detects changed meaning but is not a signature: authorized commenters can
forge payloads and recompute checksums.

Use concise reviewed summaries and safe HTTPS pointers, never raw logs, credentials,
private host coordinates or personal data. Admission and native redaction are
additional checks, not universal secret scrubbing. The plugin never fetches
pointers, reads evidence files or executes comment text.

## Writes, races and timing

Read tools perform fresh native reads only. Writers admit input, read, append at
most once, then read back exact stored bytes and reconstruct history. Failed initial
reads write nothing. Exceptions, changed/missing readback or conflicting histories
after an append return `write_unverified` with `may_have_persisted: true`: no rollback
or automatic retry is promised. Inspect history before an explicit stable-ID retry.

Read/append is not atomic uniqueness. Identical races may create multiple physical
comments representing one logical record, preserving all native occurrences. Forks,
cycles, missing predecessors and changed same-ID payloads suppress a latest winner.
A later write can invalidate a previously honest snapshot. Timestamp, list position
and lexical ID never resolve causality.

Timing is descriptive, not scheduling. Missing deployment/integration anchors stay
unknown; completion does not invent deployment time. Check returns suggestions only.
The plugin installs no completion observer. Ordinary handler/read/write errors fail
observationally; process exit, deadlock, hostile dependencies and runaway resources
remain outside that guarantee. Production native calls have no proven cancellable
hard timeout.

## Tests and removal

Production unit tests cover admission, readback, causality, timing and board fences.
Focused real-Hermes tests cover registered calls, restarts, concurrent appends,
disabled/error paths and preservation of delivery history. Test-only read-only SQL
compares full disposable history; lifecycle setup occurs through native tools.
Docker bounds the test environment, not a later live plugin. No model provider,
worker simulator or host Hermes installation is needed for these tests.

Disable/remove through native commands and verify a fresh session. Native comments
and delivery history survive removal. Builds/tests do not authorize live enablement,
profile changes, gateway restarts, pilot work or merging an unreviewed PR.
