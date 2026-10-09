# Decision: native-record logical ordering

Date: 2026-10-01.
Status: **Operator-approved direction; schemas, implementation and feasibility
acceptance still require their normal evidence and independent review.**

Jimmy approved proceeding with the recommended stable-logical-ID/predecessor
amendment and resuming the existing Phase-0 task. This approval replaces only
the clarified requirement to order observations by native comment IDs. It does
not approve Phase-0 completion, implementation delivery, publication, live
installation, a pilot environment or an additional reconciliation surface.

## Evidence and reason

The original Phase-0 findings and committed failing gate are preserved as
historical evidence. The installed public writer acknowledges a comment ID,
but the public reader returns comment author, body and creation time without
that ID. Real timestamp ties prevent treating timestamps as a total order.
The public reader still exposes the native structured record bodies required
for a small causal ordering design. No private database workaround is accepted.

## Approved amendment

- Give each contract/observation a stable logical record ID with explicit retry
  semantics. Observations remain bound to their immutable contract.
- Persist an explicit preceding-observation reference in each observation's JSON;
  the first observation has no predecessor within that contract. Final field
  names and schemas belong to the downstream reviewed ADR/schema task.
- Reconstruct a unique causal chain from record contents, not native comment
  position, native IDs, timestamps or lexicographic record-ID order.
- Diagnose orphan/missing predecessors, cycles, conflicting same-ID payloads and
  concurrent sibling/fork records. A fork is attention-worthy ambiguous project
  knowledge, not permission to choose a latest winner or change native task state.
- Identical retries are logically deduplicated while retaining source occurrences
  and native attribution. Never silently erase conflicting payloads or provenance.
- Native author/time anchor attribution and persistence, not ordering authority.
  Keep actual observation time/environment and criterion evidence distinct.
- History stays append-only in native comments. No independent persistence,
  locks with authoritative state, automatic remediation or automatic conflict
  reconciliation. A future append-only reconciliation policy would need separate
  approval; MVP exposes ambiguity honestly rather than manufacturing a result.

## Constraints unchanged

The production adapter uses only `kanban_show` and `kanban_comment`. No private
Kanban imports, database access, CLI write fallback, Hermes source changes or
upgrade. Native task/run/review/delivery history remains owned by Hermes.
No new outcome lifecycle, scheduler, fleet crawler or dashboard. Publication,
live installation/profile/dependency changes/restart/deployment and the real
pilot remain subject to their existing explicit approvals.

## Required continuation on the existing Phase-0 card

1. Update the probe/tests/report gate to the approved ordering requirement. Keep
   the observed missing native IDs as a recorded capability limitation, not a
   now-obsolete mandatory failure. Do not merely delete the failing assertion.
2. Exercise actual native append/read roundtrips with logical predecessor records;
   prove reconstruction stays invariant under reordered read input, same-second
   timestamps, duplicate retries and visible forks/conflicts. Keep this a bounded
   feasibility harness, not premature production-plugin implementation.
3. Finish actual worker/task/board-fence, restart/multi-profile, observer
   disabled/error/slow paths, broader redaction and bounded history-scaling probes.
   No manually forged worker pins or mocked dispatch are accepted as integration
   proof. If a completion hook is omitted, establish failure isolation appropriate
   to that architecture and state which hook cases are legitimately inapplicable.
4. Missing prerequisites and unexercised mandatory requirements still fail loudly;
   canonical verification must not pass by skipping or weakening remaining gates.
5. Update current findings while retaining the original no-go evidence and this
   decision. Commit the complete artifact and obtain native same-card independent
   Gilfoyle exact-SHA review before completing Phase 0 or releasing successors.

## What this decision is not

It is not a claim that all needed public interfaces are proven, that the current
canonical suite is green, or that a production plugin exists. The unchanged
historical native-ID assertion will remain red until the resumed worker replaces
it with the approved causal-ordering checks and completes the other probes.
