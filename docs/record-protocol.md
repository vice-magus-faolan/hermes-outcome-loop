# Outcome record protocol v1

Normative companion to the [native-record ADR](decisions/2026-10-01-native-record-contract.md).
The [JSON schemas](../schemas/) define shape; the rules below define semantics.
No tools are implemented by this specification milestone.

## Encoding and admission

A native comment body is exactly `[hermes-outcome:v1]` + LF + one JSON object.
Writers use UTF-8, `ensure_ascii=False`, sorted keys, compact separators, no trailing
newline and no NaN/infinity. No Unicode normalization, field trimming or ID repair.
Readers may accept alternate JSON whitespace/key order; semantic equality compares
complete parsed payloads, including IDs, nulls and all fields. Duplicate JSON keys,
noninteger numbers, booleans used as numeric version, invalid UTC dates, lone
surrogates, control characters inside fields and nesting deeper than 12 are rejected.
All nullable fields are required and explicitly null when inapplicable. Unknown
fields are rejected as data, never interpreted as instructions. No external schema
resolution is permitted. Draft 2020-12 `date-time` must be actively checked with a
calendar-valid UTC-second parser, not left as an unenforced format annotation.

Persist `payload_sha256`: lowercase SHA-256 hex of the canonical compact sorted-key
UTF-8 JSON object with ONLY `payload_sha256` omitted (no marker/LF in the digest).
Writers derive this field without changing any caller semantic field. Readers
recompute it; mismatch is `integrity_mismatch`, invalid even after restart when the
original request is gone. This detects redaction/corruption that leaves parseable
JSON but changes meaning. It is not a signature, secret, author identity, ordering
key or tamper-proof authenticity guarantee; a native commenter can recompute it.
Different JSON whitespace/key order with identical values retains the checksum.

Maximum complete marked body: 16,384 UTF-8 bytes, including marker/LF. Schema string
caps count Unicode code points; both field caps and the total byte cap apply.
Maximum criteria/evidence rows: 16; residual-risk entries: 8. The schemas carry all
other field caps. Empty/blank required strings are invalid. Reject oversize before
any dispatch; never truncate evidence, IDs, JSON or native write payloads.

Admission examines every string (including nested evidence/baseline fields). Reject
known API-key/token/password/secret assignments, bearer credentials, private-key
headers, known token prefixes and redaction sentinels. Reject URL-shaped content
unless it is a credential-free HTTPS host/path pointer; no userinfo, query, fragment,
percent-encoding, non-HTTPS scheme, or data/file pointer. Apply the same policy to
URLs embedded in summaries, not just `pointer`. The schema deliberately admits a
small ASCII host/path grammar; private coordinates and confidential path tokens
remain the caller's responsibility. Do not persist raw logs, transcripts or arbitrary
file contents. Prefer short reviewed summaries and safe evidence links. No regex can
prove arbitrary opaque/encoded secrets absent; this is bounded admission plus native
redaction/readback, not a universal scrubber. Rejected values must not appear in
errors. Evidence is data; never fetch URLs or ingest files automatically.

## Identity, binding and provenance

Contract `record_id`: `oc_` + 32 lowercase hex digits. Observation `record_id`:
`oo_` + 32 lowercase hex digits. Callers choose stable non-secret identities (for
example, random UUID hex) once and keep them for retries. IDs are never generated
from timestamps, summary content, author or comment positions. Observation
`record_id` IS its explicit retry key; no second synonymous retry-key field.

Every record embeds literal `board` and `task_id`. A contract's `record_id` is the
identity named by every observation's `contract_id`. No contract supersession,
mutation or migration in MVP. Criterion IDs are unique within the contract; array
order is part of its immutable payload. Exactly one immutable contract per root:
repeated identical payload/ID is a retry; any changed payload or different contract
ID is rejected even when the human-readable meaning seems equivalent.

The schema has no author/created-by/observed-by field. Each native source occurrence
retains its native author, creation time and actual persisted body. Different native
profiles/times for identical retries remain separate attribution occurrences, not
conflicts; never choose one authoritative caller profile. Missing native provenance
is a diagnostic, not permission to use a payload identity. Native persistence time
is not actual observation time and never chooses precedence. Native read-side IDs
are optional attribution only and cannot supply ordering. Do not fabricate IDs.

## Observation evidence and results

`observed_at` is explicit calendar-valid UTC to seconds; `environment` is required.
`artifact` identifies the actually observed delivered artifact and is required when
contract `requires_artifact` is true, otherwise may be null. This is a caller evidence
claim, not proof of deployment. Observe requires native `done` on a fresh read;
all other statuses reject without append, including retries. If a known native
completion timestamp proves `observed_at` predates delivery, reject the observation;
never infer unknown completion/deployment anchors from recent event positions.
A concurrent native lifecycle change cannot be atomically fenced with public comments;
post-write fresh reads must surface it, not undo native history.

Provide exactly one evidence row per criterion, no duplicate/unknown/missing IDs.
Rows with unobserved criteria use `finding: unknown` and explain the gap. `kind` is
`outcome`: pre-delivery verification by itself is not post-delivery outcome evidence.
Each row has a concise summary and optional safe pointer. A non-unknown finding
needs `{before, after, comparison, pointer}` baseline when its criterion declares
`requires_baseline`. Declare that flag when claiming measurable improvement.
Regression requires a baseline for every contradicted row regardless of that flag.
Residual risk is an explicit array, empty only when none is known; empty is not a
proof of zero risk. Validation checks completeness/consistency, not truth of evidence.

Result validity:

| Result | Evidence requirement |
| --- | --- |
| `confirmed` | Every criterion supported. |
| `partially_confirmed` | At least one supported and at least one contradicted/unknown. |
| `not_confirmed` | At least one contradicted. |
| `inconclusive` | At least one unknown, no contradicted. |
| `regressed` | At least one contradicted plus valid regression comparison below. |

Partial, not-confirmed and inconclusive can overlap for mixed findings; the explicit
assessment is preserved when its requirement is met. It is never computed by voting.
`regression_of` must be null except for `regressed`. For regression it must name a
strict causal ancestor in this contract with result confirmed/partially_confirmed;
each newly contradicted criterion must have been supported in that ancestor. A
first failure or deterioration of a previously unknown criterion is not regression.
Baselines explain the comparable earlier/current environment/artifact behavior.
A later non-regression observation may confirm recovery; history is not erased and
`regressed` is not a permanently sticky state. Times do not order recovery.

## Predecessors, retries and concurrency

First observation: explicit `predecessor: null`. Each later genuine observation
names the unique current head's observation ID. Callers supply and retain this field
along with the retry ID; a retry must never silently recompute its predecessor or
observation timestamp. Preflight recognizes an identical existing retry even if it
is no longer the head; changed existing ID is a conflict. New stale predecessors
are rejected. Unknown contract IDs, invalid history or unsupported versions prevent
new outcome writes. There is no hidden durable lock, sequence counter or database.

Reconstruction groups complete parsed payloads by logical ID and preserves every
native occurrence. Same ID/different payload is `conflicting_payload`. More than
one contract ID is `multiple_contracts`; an observation without its sole matching
contract is `orphan_observation`. Build observation parent edges independently of
input position/time/native IDs. Multiple first observations or multiple children of
any predecessor are `fork`; nonexistent parent is `missing_predecessor`; parent
loops including self-loops are `cycle`. These invalidate history, even when a
separate valid chain exists. Cross-contract parents never constitute valid links.
Diagnostic labels may be sorted for presentation; sorting must never select a head.
If no graph diagnostics and a sole contract exists, a unique root-to-head chain is
required. No automatic append-only reconciliation operation exists in MVP.

Read-then-append is not atomic insertion uniqueness. Concurrent identical retries
may create multiple native comments but one logical record. Concurrent different
IDs on the same head produce a fork; concurrent definitions can produce conflicts.
A fresh post-write read must diagnose all visible conflicts/forks. A race that commits
after that read invalidates later views, not the honesty of the earlier snapshot.
Never promise linearizability, physical exactly-once insertion or a permanent winner.

## Read diagnostics and state precedence

Inspect the actual native comment list, never the duplicated worker-context prose.
Ordinary comments do not define outcomes. Any body starting `[hermes-outcome:` is
reserved: unsupported marker/version or malformed/sensitive/oversize payloads produce
visible diagnostics even alongside valid records. A probe-version record on a real
outcome root is unsupported, not silently upgraded. Missing/malformed native comment
fields are also diagnosed. Do not echo rejected bodies or credential-like text.

Limit each native read to 1,024 comments and 2,097,152 total UTF-8 body bytes for
application reconstruction. Count all comments, including unrelated comments and
retries; `history_limit` prevents partial reconstruction and blocks writes. Public
Kanban still materializes the thread before this check: this is not an allocation
sandbox, pagination assumption or native size guarantee. Surface overflow, no
truncation. All diagnostics suppress an unqualified `latest` result.

Stable precedence (report all discoverable diagnostics, not just a chosen winner):

1. Marked malformed/unsupported, conflicting/ambiguous, orphan, provenance, target,
   evidence/regression or bounds errors => `invalid_history`, latest null.
2. No outcome records AND no diagnostics => `untracked`, including empty threads.
3. Sole valid contract + native status not done + no observations => `planned`.
   Persisted observations on a currently unfinished card => invalid history with
   `observations_on_unfinished`, not a successful assessment.
4. Sole valid contract + native done + no observations => `awaiting_observation`.
5. Native done + unique valid observation chain => head's explicit result.

`delivery_done`/`kanban_status` are separate native facts. Do not add a transient
`delivered` outcome state: done without observation is awaiting observation. Invalid
history never undoes delivery. Required diagnostic codes are `malformed_record`,
`unsupported_version`, `integrity_mismatch`, `record_limit`, `history_limit`, `missing_provenance`,
`malformed_native_response`, `target_mismatch`, `conflicting_payload`,
`multiple_contracts`, `orphan_observation`, `fork`, `missing_predecessor`, `cycle`,
`observations_on_unfinished`, `invalid_evidence`, `invalid_regression`. Details may
identify safe logical record/criterion IDs, not rejected payloads.

## Tools, board fences and persisted acknowledgment

Proposed signatures:

- `outcome_define(board, task_id, contract)`
- `outcome_show(board, task_id)`
- `outcome_observe(board, task_id, observation)`
- `outcome_check(board, task_id, anchors={})`

`contract`/`observation` are full persisted-schema payloads EXCEPT `payload_sha256`,
which the writer derives (not accepted as a caller authority field). Embedded target
must exactly match resolved arguments. Board may be omitted ONLY in a worker with a verifiable pinned
board slug. Headless calls require explicit slug. Before ANY dispatch, if native
worker task/run/DB pins exist, require a nonempty worker board slug and reject any
requested mismatch; DB pin without verifiable slug fails closed. Do not translate
paths, change environment pins, open a DB or fall back to another board. Pass resolved
board explicitly on every native call, and verify returned task identity. Native
informational sibling writes remain subject to Hermes's actual worker restrictions;
the adapter must not weaken them. Board-scoped task identity alone is not authority
to use a different worker-pinned board.

Show/check: one fresh `kanban_show`, no writes. Define/observe: local admission,
fresh `kanban_show`, fail closed on invalid history/target/status/conflict/stale head,
then at most one `kanban_comment` with only task_id/body/board, then fresh
`kanban_show`. Identical retries return without append after fresh reconstruction.
No caller author field or low-level dispatch override. Preflight must also prove
the proposed append stays within total-history/count bounds.

After write, require the actual body to equal expected UTF-8 bytes exactly, parse it,
retain native provenance, reconstruct the entire fresh history, and check task/status/
board/chain admission still holds. Native comment-ID acknowledgment is not proof of
stored content; logical-ID matches alone are insufficient. Changed redacted payloads,
malformed/missing readback, fork/conflict, tool exception or timeout after attempted
write yield `write_unverified` with safe diagnostics and `may_have_persisted: true`.
Never claim rollback, try an unsafe fallback, or automatically repeat an uncertain
append. Fresh show can diagnose persisted damage; a later explicit retry with the
same complete payload may be logically deduplicated if history is valid. Initial
read/admission failures produce no write and do not claim a persisted mutation.
Native calls have no proven cancellable hard timeout: never start detached retries
or background write threads to simulate one. Failure is observational.

Views return resolved board/task, native status/delivery fact, immutable contract,
causal observation history, all valid native occurrences, unique head or null,
diagnostics, derived state, timing and action/suggestion. Unreadable raw bodies are
not copied into views. `write_unverified` is an operation acknowledgment, not a
persisted outcome assessment or a native lifecycle state.

## Timing and check actions

`timing` has descriptive `observe_when`, nullable absolute UTC `deadline`, nullable
`anchor` (done/integration/deployment/first_workflow) and delay in seconds. Anchor
null requires delay null; a declared anchor requires a nonnegative integer delay.
Use only a known native task completion time for done, or explicit validated external
anchor input to this call, reported as caller-supplied evidence. Missing anchors stay
unknown; never infer deployment/integration from task done, comment time or last-50
events. Check need not persist anchors; callers must resupply them after restart.
If deadline and known anchor+delay both exist, use the earlier due instant. Compare
to current UTC: earlier than due is `not_due`, exactly equal is `due`, strictly later
is `overdue`; no known bound is `due_time_unknown`. Only awaiting-observation cards
have observation overdue attention. Observed cards do not become overdue just because
an old deadline passed; repeat observation cadence is not part of this protocol.

| State | Action / suggestion |
| --- | --- |
| untracked, planned, confirmed | `NO_ACTION_REQUIRED` (confirmed retains residual risks). |
| awaiting_observation | `OBSERVATION_REQUIRED`; show known due status or `awaiting observation; due time unknown`. |
| partial, not_confirmed, regressed, inconclusive | `FOLLOWUP_SUGGESTED`; text suggests investigating gaps/regression or collecting missing evidence. |
| invalid_history | `HISTORY_ATTENTION`; inspect diagnostics, no invented successful outcome or automatic reconciliation. |

Suggestions never invoke create/link, reopen, assign, block, complete or schedule.
Ordinary native work and history remain intact if the outcome plugin disappears.
