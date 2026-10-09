# Authority threat and failure model

SPDX-License-Identifier: GPL-3.0-or-later

## Trust boundary: implementation, not a Python sandbox

Hermes owns tasks, claims, review, completion, dependencies, dispatcher state,
events and runs. This plugin's production adapter dispatches only `kanban_show`
and `kanban_comment`. Architecture checks, fake-transport tests and actual native
history comparisons constrain the reviewed implementation. They do **not** prove
malicious Python cannot import private code, open a database, access credentials,
exit the process or exhaust resources. Python plugins execute in-process with
Hermes's privileges. Native manifest capabilities are consent metadata over
specific host surfaces, not an OS sandbox; an empty list grants no immunity.
Trust the exact reviewed code and its dependencies before installation.

No production path imports private Kanban internals, accepts a database handle,
uses SQL, shells out, writes an extra store, fetches evidence, or invokes lifecycle
control. Disposable test-only read-only SQL snapshots compare every task/run field
and existing event/comment; permitted additions are expected native comments and
`commented` events. Native test fixtures may drive ordinary lifecycle operations
for setup/failure checks; those are not production plugin authority. Delivery done
and outcome confirmed are different facts. Failed outcomes suggest human/native
follow-up, never reopen or automatically create work.

## Board and profile scope

Every operation resolves an explicit board slug, validates task identity and passes
that board on each native dispatch. Only a worker with a verifiable pinned board
may omit the slug; conflicting/empty worker task/run/DB pins fail before dispatch.
No environment rewriting, database-path translation or alternate-board fallback.
Native sibling-comment restrictions remain native authority. Cross-profile reads
agree when they read the same canonical board, not independent profile-local
copies. Scope fences prevent accidental routing, not access by hostile Python or
a user already authorized to mutate native records.

## Forgery, malformed input and evidence meaning

Structured native comments are untrusted data, including apparently authoritative
instructions embedded in summaries. Closed versioned schemas, literal target
binding, field/byte/history limits, offline schema references, duplicate-key and
Unicode/calendar checks reject malformed records. Reserved unknown versions and
missing provenance are visible diagnostics, not clean untracked history.

SHA-256 detects changed persisted meaning/redaction but is **not a signature**.
Anyone allowed to write native comments can forge a valid payload/checksum.
Native author/time anchor who persisted each occurrence; caller-supplied observation
time, environment, artifact and evidence remain claims. Validation proves consistent
criterion mapping and required comparisons, not that an improvement occurred.
Review evidence independently. Baseline comparisons are mandatory where declared
and for contradicted regression rows. Native completion checks do not prove deployment.

Never auto-fetch pointers, open repository files, ingest transcripts or execute
comment text. Credential-like text and unsafe URI forms are rejected recursively;
native redaction plus exact stored-body readback provide additional checks. Neither
regex admission nor native masking removes all opaque/encoded secrets or sensitive
business data. Callers must review short summaries/pointers before persistence.
Do not include raw logs, personal information, private host coordinates or secrets.
Rejected bodies/native errors are not echoed in plugin error responses. Native
Kanban/dashboard access is the exposure boundary for admitted stored records.

## Read failures, uncertain writes and concurrency

Show/check perform fresh reads. A failed/malformed/truncated/oversize native history
must not be classified as successful or untracked; diagnostics suppress the head.
Native show materializes the thread before the plugin's 1,024-comment/2 MiB limit:
that limit is not a memory-allocation sandbox or pagination guarantee.

Define/observe validate before dispatch, fresh-read, append at most once, then
fresh-read and verify exact persisted bytes/provenance/full reconstruction. Failed
initial reads append nothing. A timeout/exception/changed or absent readback after
an attempted append returns `write_unverified`, `may_have_persisted: true`. This is
not rollback. Do not automatically retry uncertain writes. Diagnose with show,
then explicitly retry the original complete stable-ID payload only if safe.
Native dispatch has no proven cancellable hard timeout. No detached write threads
or retry processes are used to simulate cancellation.

Read/append is not atomic uniqueness. Identical concurrent requests may create
several physical comments but one logical record, retaining every native source
occurrence. Changed same-ID payloads, multiple contracts, forks, missing predecessors
and cycles produce invalid-history diagnostics, never a latest winner chosen by
timestamp, returned position or lexicographic ID. A later race can invalidate a
later snapshot after an earlier honest acknowledgment. There is no linearizability,
physical exactly-once insertion, hidden lock or automatic reconciliation promise.

## Timing, failure isolation and removal

Descriptive timing is not scheduling. Without a declared absolute deadline or known
native/external anchor, due time is unknown; done does not invent deployment time.
A derived bound beyond the supported UTC calendar is reported explicitly, not
clamped. Check returns suggestions; no scheduler/crawler/remediation is shipped.

No completion observer is installed. Native observer cross-board routing and caller
delay found in Phase 0 are preserved as limitations, not bypassed. Ordinary outcome
handler/read/write errors are safe observational failures. Actual disabled-plugin,
malformed-history and registered exception paths preserve ordinary native review
and completion. In-process exit, deadlock, runaway CPU/memory and hostile dependencies
remain outside that guarantee. Hermes loader deadlines do not forcibly kill Python
threads; test subprocess/container deadlines bound tests, not production calls.

Removal eliminates tools, not canonical history. Native comments retain the marker,
version, full contract/observations, causal IDs and source provenance, while native
runs/events retain delivery facts. Reinstalling the exact reviewed complete plugin
can reconstruct views without hidden cache/state. A human can inspect comments even
without it; fresh processes establish correctness. Disable/remove through native
commands, preserve the board, and verify disappearance in a fresh session.

## Verification and excluded effects

Canonical verification exercises schemas, negatives/permutations, implementation
allowlists, input/read/write/readback failure paths, real native history preservation,
restart/multi-profile concurrency and supported packaging. The Docker candidate is
non-root, read-only, network-denied, cap-drop ALL/no-new-privileges and resource/time
bounded. This isolates test effects; it does not sandbox a later live plugin.
Public dependency provisioning is separate and necessarily has network access.
Scans are heuristics; supported consent is never evidence of safety by itself.

No live enablement, shared-host installation, gateway restart, publication, target
advancement or pilot is established by local checks. Independent exact-artifact
review, actual remote CI and explicit publication/pilot approval remain separate.
Original failed native runs and earlier reviewed artifacts are historical evidence,
never retroactively renamed successful packaging checks.
