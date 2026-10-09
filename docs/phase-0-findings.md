# Phase-0 public-interface findings

Execution-path update, 2026-10-09: the findings and receipts below are preserved
historical evidence, not a current host-side preparation instruction. The
[Docker recovery decision](decisions/2026-10-08-docker-test-recovery.md) and
[integration report](docker-integration.md) govern new native runs. The actual
pinned Docker build and 101-test canonical suite now pass, including the original
required real Phase-0 worker/observer/record tests and new production-native gates.
This is fresh builder execution evidence, not retroactive acceptance of the failed
host runs or independent integration review. Packaging, publication and pilot
remain separately gated; a runner smoke alone is not Phase-0 re-attestation.

## Current continuation — 2026-10-01

**GO to independent Phase-0 review for the approved native-record direction.**
This is builder-verified feasibility evidence, not reviewer acceptance, production
implementation, schema approval, publication or pilot authorization. The original
2026-09-30 NO-GO artifact is retained below as historical evidence. The operator
amendment changed only the ordering requirement; the resumed probes satisfy the
remaining required contexts rather than simply removing an assertion.

### Runtime and current official interfaces

The continuation still executes installed Hermes
`0.21.5+4905.gf42f579`, full source SHA
`f42f579cf8bac4918ac9599bece71618afadd846`, with its already provisioned
Python `3.14.7` dependency venv. Read-only Git checks found the installed source
clean before and after the real CLI worker. No source, shared dependencies, live
profiles, gateway or integration target was changed.

Current official pages were retrieved on 2026-10-01 using
`python3 scripts/phase0_docs.py` after the extractor returned 403 errors:

| Public documentation | HTML bytes | SHA-256 receipt |
| --- | ---: | --- |
| [Plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins) | 530074 | `1da56f8cd7ce2b584aecca3f5322b4cb6799436938885173c0b80b15db191dae` |
| [Kanban reference](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban) | 269859 | `92cb526213b1d6429810b6c5cd67f4ddfee824ea271799a3f20eab74d359d436` |
| [Hooks reference](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks) | 544750 | `20d31aa6cef06bfb62ca1ad86f6428d3a4b8ee99d2d74fe7b826f9236b128f4a` |

The pages document `ctx.dispatch_tool`, native profile identity, post-commit
Kanban observers, board isolation and logged/skipped observer exceptions.
These are current published-document receipts, not an upstream source SHA or
proof that every documented guarantee holds on the installed version. The
runtime discrepancies below take precedence over broad documentation wording.
No Hermes update was performed to reconcile those differences.

### Reproduction and isolation

Use the same explicit `HERMES_PHASE0_SOURCE`, `HERMES_PHASE0_PYTHON` and writable
`TMPDIR` prerequisites described in the historical reproduction section. Current
commands are:

```sh
python3 scripts/phase0_probe.py --require-feasible
python3 -W error::ResourceWarning -m unittest discover -s tests -p test_phase0.py -k HarnessSafetyTests -v
python3 -m unittest discover -s tests -p test_phase0_ordering.py -v
python3 scripts/phase0_audit.py
python3 scripts/verify.py
```

The extended harness requires Linux `/proc`, POSIX process groups, a loopback
HTTP listener, Git, repository Python 3.12+ and the installed dependency venv.
No package installation, model account or external model endpoint is required.
Missing prerequisites or unsupported behavior fail, never skip. CI must provision
these explicit prerequisites; no claim is made about the old bootstrap-only CI.

`phase0_probe.py` allowlists the initial child environment and creates fresh
HOME/profile/Kanban/scratch roots. Pre-import checks reject ambient worker/DB
pins, symlink escapes and existing boards. Project plugins are disabled. The
fixture is loaded by the real PluginManager and calls actual `ctx.dispatch_tool`.
The real dispatcher supplies worker task/run/DB/profile pins; the harness never
forges them. A scripted loopback OpenAI-compatible model transport chooses the
fixture tool in a real `hermes chat -q` worker; it does not replace dispatch,
native tool handlers, lifecycle hooks or the agent loop. Verdicts come from native
reads, native attribution and completed runs, not scripted model claims.

The only CLI Kanban operation in the harness is the public dispatcher launch:
there is no CLI data-write or redaction fallback. The dispatcher uses a disposable
wrapper pinned to the provisioned interpreter and installed module; supported
`HERMES_DISABLE_LAZY_INSTALLS=true` prevents launch-time provisioning. Fixture
configuration uses `platform_toolsets.cli` and disables deferred tool search so
the scripted model receives the probe tool. An earlier continuation attempt omitted
that configuration and produced no tool calls; it is not accepted worker evidence.

The public `on_kanban_worker_spawned` hook records disposable cleanup PIDs only.
The parent keeps the scripted transport alive until worker exit, then performs
bounded cleanup. Timeout cleanup validates each recorded process's disposable HOME
and process-group identity before signaling. Files, native records, model request
bodies and local diagnostics are destroyed with the temporary tree; public reports
contain only portable measurements and booleans, never snapshots or live coordinates.

`phase0_snapshot.py` opens only the fixed, resolved disposable database with
SQLite `mode=ro`, solely to compare full native task/run/event/comment history
and actual stored text against public reads. It neither mutates SQL nor supplies
IDs/order to reconstruction. The fixture does not import it. Production must not
import this helper or access the database.

### Go/no-go by handoff prerequisite

| Prerequisite | Current evidence / decision |
| --- | --- |
| Installed identity and current official interfaces | GO for the recorded installation and receipts, not future version compatibility. |
| Native append after done | GO: structured comments append after actual completion; task/run rows and pre-existing events remain intact, with only native `commented` additions. |
| Complete record bodies and native provenance | GO: full public comments through 1024 records; native author/body/time agree with read-only stored-history comparisons. Native comment IDs remain absent. |
| Deterministic logical ordering | GO: native JSON roundtrips reconstruct the same unique chain after reversed/rotated input and tied timestamps; identical retries retain each source occurrence. Forks, multiple roots, conflicting same-ID payloads, missing predecessors and cycles return diagnostics and no winner. |
| Actual concurrent append | GO: two fresh profile processes read one shared predecessor before a test-only barrier releases both native appends. Both authors survive; reconstruction diagnoses a fork, with no winner. No authoritative lock/store is added. |
| Registered headless and worker dispatch | GO: actual PluginContext dispatch reaches native handlers in library-host and real dispatcher-spawned CLI agent contexts. Worker completion is visible as a native completed run, and worker exit is observed. |
| Native task and board fences | GO with an explicit adapter admission check: sibling lifecycle completion is refused specifically by the native task-ownership fence; same-board sibling informational comments remain allowed and preserve lifecycle history. Cross-board tasks are unavailable under the native DB pin. |
| Restart and multi-profile consistency | GO: fresh profile processes reopen the same native history; an identical retry from another profile groups logically while retaining both native authors/times. No hidden process-local outcome state is needed. |
| Canonical completion and observer exceptions | GO for bounded ordinary exceptions: callbacks freshly see done/completed event/completed run; an intentionally raised callback exception does not undo completion or prevent the later observer. |
| Disabled observer/plugin | GO: a fresh profile with no fixture enabled completes the task via a native public tool and reads its native completed run. |
| Slow observer | GO only for post-commit lock release: a 200 ms callback delays the caller, while another thread's native comment append finishes during the callback. Not a callback timeout or process-wide guarantee. |
| Cross-board completion-hook routing | NO-GO as an authority source on this installation: completing on an explicit second board emits the ambient first-board slug, so the observer's fresh read fails. Omit the optional hook; correctness must use explicitly scoped fresh reads. |
| Stored redaction and acknowledgment | GO for a guarded/readback path, NO-GO for blind trust in redaction: safe Unicode/quotes roundtrip; token-like summaries/IDs/predecessors change, and an environment assignment can destroy JSON syntax. Changed/unparseable records are not acknowledged as successful. |
| Credential-like URL admission | Native opaque query-token redaction is NOT provided by this writer. A bounded fixture admission guard rejects the exercised credential-bearing URL before a write. The production ADR must define robust sensitive-evidence rejection rather than copy this small regex as a universal scrubber. |
| Record length and rejection | GO for bounded experiments: 16 KiB total UTF-8 serialized record roundtrips at the exact boundary; one byte beyond is rejected before mutation. Native 4/16/64 KiB exploratory writes remain exact. Empty/blank and caller-author fields are rejected. The native maximum is deliberately not claimed or needed with an application cap. |
| Interactive one-thread read/parse cost | GO within measured bounds: fresh read plus causal reconstruction tested at 16/128/512/1024 small records and 128 full-sized records totaling 2 MiB. Record-count and total-byte overflow produce visible diagnostics. Not an SLO or fleet/remote-storage benchmark. |
| Whole delivery-history preservation | GO: authorized disposable read-only comparisons retain task/run rows and every pre-existing native event/comment beyond the public last-50-event window; exactly 1025 new native comment events are permitted in the count-limit probe. |
| No forbidden production API required | GO: reconstruction uses public record bodies; production can remain `kanban_show`/`kanban_comment` only, with admission checks and no required hook. No private mutation API, DB ordering workaround or CLI write fallback. |

The envelope names and 16 KiB / 1024-record / 2 MiB experiment bounds are NOT
approved production schemas or limits. The downstream ADR owns those decisions.
The observations establish a viable bounded design, not atomic uniqueness or
automatic fork reconciliation. When native writes alter a record, failure after
readback does not roll back that append; later reads must expose invalid history,
never pretend it is untracked. Opaque secrets and encoded/novel credential forms
cannot be guaranteed absent by regex redaction. Known sensitive inputs should be
rejected before append; no evidence pointer may be fetched automatically.

### Measured cost and verification

A representative required-gate run exited 0 with `feasible: true` and all required
probe sections exercised. Fresh-read/causal-parse measurements (10 samples each):

| Thread | Median ms | Maximum ms | Public response bytes |
| --- | ---: | ---: | ---: |
| 16 small records | 2.914 | 3.578 | 10598 |
| 128 small records | 6.022 | 7.289 | 40648 |
| 512 small records | 14.730 | 16.375 | 122062 |
| 1024 small records | 24.670 | 62.969 | 230700 |
| 128 records at 16 KiB each (2 MiB total) | 23.638 | 25.050 | 2179702 |

These are local warm measurements including native tool dispatch and worker-context
serialization, not performance guarantees. Public reads still materialize the whole
comment thread before application admission checks; rejecting an over-limit history
does not cap native read allocation. Do not describe this as a resource sandbox.

The ordinary-error callback completed in 24.622 ms; normal completion in 18.965 ms;
the intentional 200 ms callback completed in 221.009 ms with its parallel write
finished. A nonterminating callback can still hang its caller. Omit the optional
hook to remove this outcome-plugin completion dependency. Python process exit,
exhaustion and malicious plugin code remain outside the isolation guarantee.

The canonical verifier discovers the expanded unit/native suites and runs the
conservative AST complexity audit. Maximum harness function score is 14, with
soft warnings above 10 and failure above 15. Warning functions are explicit
boundary/diagnostic checks exercised by the native corpus; no >15 exception is used.
The prior obsolete-ID gate was replaced by mandatory causal/context/record tests,
not by a skipped integration test or constant feasibility assertion.

Actual continuation checks:

- `python3 scripts/verify.py`: 21 discovered tests passed, exit 0, including
  mandatory real-runtime worker and record probes.
- ResourceWarning-as-error harness suite: eight tests passed, exit 0.
- Causal reconstruction suite: six tests passed, exit 0. A controlled temporary
  mutation selecting the lexicographically largest ID instead of the causal head
  made the reordered/tied-time regression fail; restoring the causal logic made
  it pass. The mutation is not retained in the artifact.
- Required feasibility CLI: exit 0, `feasible: true`, `not_exercised: []`.
- Removing both runtime prerequisite variables from canonical verification:
  exit 1, integration setup error naming `HERMES_PHASE0_SOURCE`, not a skip.
- Conservative complexity audit: 74 functions, maximum 14; exit 0.
- `git diff --check`: exit 0. Installed source remains clean and unchanged;
  integration-target advancement and publication are not part of this work.
- Official-doc receipts refreshed at `2026-10-01T20:31:38.019778+00:00` match the
  byte counts and hashes above. Retrieval is explicit, not an offline-suite side effect.

## Historical artifact — 2026-09-30 (unchanged evidence below)

Status of the original 2026-09-30 artifact: **NO-GO under the original approved MVP constraints.**

On 2026-10-01 the operator approved the [logical-ID/predecessor ordering
amendment](decisions/2026-10-01-record-ordering.md) and resuming Phase 0. The
historical evidence below is preserved, not retroactively turned into a pass.
Remaining probes, updated canonical checks and independent review are still
required; there is no current feasibility or implementation acceptance.

Original finding: feasibility is incomplete;
this is a recoverable evidence artifact, not an approved plugin or delivery.
The Phase-0 stop rule applies. Implementation and schema successors must remain
gated until the operator accepts a revised requirement or a supported interface
satisfies native-ID reconstruction, followed by completion of the remaining probes
and independent exact-artifact review. No constraint/source handoff was rewritten.

## Runtime and documentation identity

Observed on 2026-09-30:

- Installed Hermes: `v0.21.5+4905.gf42f579`, release date `2026.9.24`.
- Full installed source SHA: `f42f579cf8bac4918ac9599bece71618afadd846`.
- Python: `3.14.7`; CLI version output reported OpenAI SDK `2.24.0`.
- The source checkout was clean before probing. No Hermes update, live-profile
  install, gateway restart, publication or integration-target advancement was made.
- Successful probes embed the public plugin/tool library using the installation's
  already provisioned dependency venv, preserving its `bin/python` symlink. They
  are real registered-plugin/headless-library evidence, **not a dispatched worker
  or `hermes chat -q` execution**. No model call or fake dispatch adapter is used.

Current official documentation was fetched independently of the installed tree:

- [Documentation index](https://hermes-agent.nousresearch.com/docs/llms.txt)
- [Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
  — `ctx.dispatch_tool`, `ctx.profile_name`, registration and post-commit hooks.
- [Kanban reference](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
  — native tool versus human CLI surfaces and named board routing.
- [Event Hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)
  — observer callback errors are isolated/logged; not every hook is passive.

The first text-extractor responses for the long pages were suspiciously short.
Direct HTTPS retrieval of the published plugin and Kanban HTML supplied the full
pages. Retrieval receipts (whole HTML, not normalized content):

| Page | Bytes | SHA-256 |
| --- | ---: | --- |
| Plugin developer guide | 529458 | `e543b5be7573ea60304ed2a07fddc60e24799fc8e6d2a8d3deb80e29be3b3bcc` |
| Kanban reference | 269859 | `fc21230a8c07de9fd77da3796e0174e421b9a5a7c54f9d38df306131146b10c9` |

These are receipts for current published pages, not an upstream code SHA or a
promise that their current wording matches the installed runtime. The plugin
page documents session-agnostic dispatch, native author/profile identity and
post-commit lifecycle hooks. Installed dispatch and the successful completion
observer agree with those particular claims. Documentation describing the normal
approval/redaction/budget pipeline must not be read as a sandbox or proof of
worker fencing; those contexts have not been exercised. No inspected public
interface supplies an ID-bearing comment history on this installation.

## Reproduction and harness boundaries

Set these two explicit prerequisites to the read-only installed checkout and its
already provisioned dependency venv; do not substitute a bare store interpreter:

```sh
export HERMES_PHASE0_SOURCE=/absolute/path/to/hermes-agent
export HERMES_PHASE0_PYTHON=/absolute/path/to/provisioned/venv/bin/python
python3 scripts/phase0_probe.py
python3 scripts/phase0_probe.py --require-feasible
python3 -W error::ResourceWarning -m unittest discover -s tests -p test_phase0.py -k HarnessSafetyTests -v
python3 scripts/verify.py
```

Prerequisites: POSIX process groups, Python 3.12+ for repository checks, the
installed Hermes source and its compatible provisioned dependency venv, Git, and
an existing writable `TMPDIR` scratch root. No package installation is performed
by the successful harness. Missing prerequisites fail loudly, never skip.
`--debug-runtime` exposes local error diagnostics with runtime-root paths removed;
do not publish such diagnostics as evidence. The report contains portable facts,
not task IDs, live paths, secrets, board snapshots or raw transcripts.

`phase0_probe.py` creates a fresh disposable subtree under `TMPDIR`; child HOME,
Hermes profile, Kanban home and temporary paths are all replaced. The child env
is allowlisted: inherited board DB/task/run pins, profile routing, plugin flags
and credentials are not forwarded. Before importing Hermes, the inner probe
rejects unknown Hermes overrides, resolved-path/symlink escapes and pre-existing
board databases. Its working directory is disposable and project plugins are
disabled. Named boards are fixed synthetic slugs, not caller-controlled paths.
The subprocess group is killed/reaped on timeout and after completion before
removing the disposable tree. This constrains this harness; it is not a sandbox
against malicious Python or a privileged external process racing the filesystem.

The fixture is discovered/enabled from its disposable profile via the actual
PluginManager. A genuinely registered fixture handler invokes **actual**
`ctx.dispatch_tool`; it never replaces dispatch or native handlers. Native
`kanban_create`/`kanban_complete` are permitted only for disposable test setup.
The future production adapter remains limited to `kanban_show`/`kanban_comment`.
No private Kanban imports, direct SQL writes, DB reads, live board operations or
CLI Kanban write fallback occur in these probe scripts.

An initial unsuccessful launcher-bootstrap experiment attempted to provision
products inside a fresh disposable HOME and timed out; it produced no accepted
integration evidence. Its disposable files were removed. The corrected harness
uses the already provisioned venv and deliberately does **not** import CLI
`hermes_bootstrap` (launch preparation can provision dependencies). A regression
also preserves the venv interpreter symlink; resolving that symlink collapses
the launch contract to the bare interpreter. Never solve isolated import failures
by updating Hermes or its shared dependencies.

## Observed results and handoff prerequisites

Representative successful evidence-collection invocation:

| Prerequisite | Result / decision |
| --- | --- |
| Installed identity + current public docs | GO for the recorded installation; receipts above. |
| Append after canonical done | GO: four structured records appended/read back after native completion. Task row and completed runs unchanged; all pre-existing public events retained; exactly four native `commented` additions. |
| Native author/time | GO in the disposable headless profile: author `phase0-a`, integer native creation timestamps; callback profile also `phase0-a`. Not cross-profile proof. |
| Full ID-bearing deterministic history | **NO-GO**: append acknowledges distinct increasing `comment_id` values; reads contain only `author`, `body`, `created_at`. All eight small-probe comments are visible, but native IDs are lost. No large-history completeness claim. |
| Same-second ordering | **NO-GO**: real same-second timestamp ties observed in the four-record burst. Incidental returned order is not a supported native-ID tie breaker. |
| Registered plugin/headless dispatch | GO within the library-host context: real registration and dispatch reach native handlers without CLI agent attachment. |
| Worker dispatch/task/board fences | NOT PROVEN: no dispatcher-spawned worker was run. The harness intentionally strips live worker pins; manually copying them is not integration evidence. |
| Explicit board routing | GO for headless calls: a task on the second disposable board is visible there and absent on the first. Worker DB pins/fences remain unproven. |
| Canonical completion observer | PARTIAL GO: callback fires through real native completion, freshly reads `done`, a completed event and completed run. No synthetic hook invocation. |
| Disabled/error/slow observer paths | NOT PROVEN: deferred under the stop rule. No process-wide isolation claim. Hook remains optional; fresh reads suffice architecturally. |
| Tool redaction vs deterministic JSON | PARTIAL GO: safe JSON round-trips exactly; one synthetic token-like string is redacted in storage, safe record ID retained, JSON remains parseable. Payload meaning changed. Broader redaction corpus still needed. |
| Record sizes/rejection/readback | PARTIAL GO: 4161, 16450 and 65602 UTF-8 byte records were stored/read back exactly; empty body rejected. Native maximum not established; oversized-record rejection is not yet implemented or proved. |
| Single-thread read/parse cost | PARTIAL GO: 20 fresh reads with eight comments; representative median 3.103 ms, maximum 3.761 ms, serialized public response 96961 bytes. Local warm measurements only, not an SLO or large-thread scaling evidence. |
| Multi-profile consistency/restart | NOT PROVEN: deferred under the stop rule. |
| No forbidden production API needed | NO-GO for the current ordering requirement. All successful probe operations use public dispatch; supplying the missing IDs through private DB access would violate the adapter boundary. |
| Overall MVP feasibility | **NO-GO; stop, preserve evidence, block this same task.** |

The public reader exposes only the last 50 events and duplicates comment content
into worker-context text. Therefore the successful event-preservation assertion is
bounded to the small test, not proof about whole canonical histories. Later
integration may use authorized read-only snapshots of **disposable** DB history
solely for comparisons, never as production persistence or an ID workaround.

## Installed source corroboration (read-only inspection, not runtime evidence)

At the recorded full SHA:

- `tools/kanban_tools.py:404` projects comments to author/body/created_at;
  `:637-656` implements public show, including the last-50-events cap;
  `:892-911` forces redaction, derives trusted author and returns write-side ID.
- `hermes_cli/kanban.py:496` also omits IDs from CLI JSON comment history.
  `:749-760` permits a caller author and optional truncating `--max-len`, then
  sends the body to the lower layer without the tool's explicit forced redaction.
- `hermes_cli/kanban_db.py:1769-1784` validates nonblank body/author and inserts
  them; it is not the forced-redaction boundary. `:1798-1799` orders that history
  by creation time alone. Reading this source is not permission to import it into
  the adapter, or to rely on incidental SQL tie ordering.
- `hermes_cli/plugins.py:705-714` performs actual scoped registry dispatch.
  `hermes_cli/kanban_db.py:2822-2834` records completion and invokes the observer
  after the native transaction. The normal callback's public fresh read confirms
  committed visibility; callback error/timeout behavior is source-described only.

Thus CLI writes are **not** an equivalent fallback: they have different author,
redaction and optional truncation semantics. No CLI redaction mutation probe was
run. Redaction during terminal display is also not evidence that stored text was
redacted. Future outcome writes must reject oversized payloads and read back,
parse and compare the actually stored record before acknowledging success;
reject redacted IDs or changed contract semantics, never bypass redaction.
A proposed initial plugin cap of 16 KiB total UTF-8 serialized record (including
marker) is below exercised storage sizes, but is **not an approved schema limit**.

## Smallest proposed adjustment — decision required, not implementation

Do not change Hermes, read private comment IDs, add an outcome DB/lock, use CLI
writes or sort tied timestamps as if they were an authoritative sequence.

Candidate native-record-only amendment:

1. Keep one immutable contract and stable explicit logical record/retry IDs.
2. Add an observation predecessor ID (or equivalent explicit causal reference)
   within the deterministic JSON persisted through native comments.
3. Reconstruct a unique predecessor chain, independent of native comment order;
   diagnose missing predecessors, cycles, or same-ID/different-payload conflicts.
4. Concurrent siblings produce diagnosed forks. Do not pick a "latest" winner by
   timestamp, returned position or lexicographic ID. Surface ambiguous history
   until an explicitly specified append-only reconciliation operation is approved.
5. Preserve native author/time for attribution/persistence, not ordering authority.
   Logical duplicate grouping must retain and report contradictory provenance.

This changes the reviewed native-comment-ID ordering requirement, so **operator
approval is required** before modifying constraints, schemas or the gate. The
alternative is waiting for an authorized supported native ID-bearing read with
explicit order semantics; upgrading Hermes is outside this task's effects.
After a decision, finish actual worker/fence, restart/profile, observer-failure,
redaction corpus and large-thread probes, then obtain independent review on the
same card/lane. This artifact neither approves the amendment nor releases work.

## Actual verification outcomes

- Evidence collection: `python3 scripts/phase0_probe.py` exits 0 and reports
  `feasible: false`. Collection success is **not** feasibility success.
- Required gate: `python3 scripts/phase0_probe.py --require-feasible` exits 1.
- Harness safety suite with ResourceWarnings treated as errors: seven tests pass.
- Canonical `python3 scripts/verify.py`: 13 tests discovered, 12 pass, one fails
  specifically because required public native comment IDs are absent (exit 1).
- Controlled regression RED/GREEN: temporarily restoring symlink resolution
  makes `test_interpreter_symlink_keeps_venv_launch_contract` fail with the expected
  interpreter-path mismatch; preserving the symlink restores GREEN.
- Missing runtime prerequisites are errors, never an integration skip. Existing
  bootstrap-only GitHub CI does not provision Hermes and cannot pass this expanded
  command without explicit runtime provisioning. No CI/publishing claim is made.

The canonical feasibility assertion also refuses a report with unexercised
requirements even if native IDs become available later. Do not turn this evidence
collector into an acceptance shortcut by deleting the pending-prerequisite gate.
