# Phase-0 public-interface findings

Status: **NO-GO under the approved MVP constraints.** Feasibility is incomplete;
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
