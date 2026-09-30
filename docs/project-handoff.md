# Hermes Outcome Loop

## Project Goal

Build the **smallest native-Hermes extension necessary to add**

**objective → delivery → observed outcome**

semantics to Hermes Kanban without introducing another source of authority over task execution.

The extension should answer a question that native Kanban intentionally does not:

> We successfully delivered the work. Did the delivery actually produce the project outcome we intended?

This is **not** a replacement for Kanban, Project Stewardship, a project-management system, or an organizational control plane.

It is a thin outcome-observation layer around native Hermes Kanban.

Working repository/plugin name:

`hermes-outcome-loop`

---

# 1. Problem

Hermes Kanban gives us strong execution semantics:

```text
work requested
    ↓
claimed
    ↓
implemented
    ↓
reviewed
    ↓
verified
    ↓
completed
```

Our existing delivery controls strengthen this further with exact-artifact review, integration enforcement, canonical verification, and delivery provenance.

However:

```text
TASK DONE ≠ PROJECT IMPROVED
```

A completed card proves that its delivery contract was satisfied.

It does not necessarily prove:

- the intended behavior is actually usable;
- the change improved the project;
- the original problem disappeared;
- an operational metric changed as expected;
- the improvement persisted after deployment/use;
- no important regression appeared afterward.

We need a lightweight mechanism for expressing an expected result before delivery and recording evidence after delivery.

---

# 2. Core Principle

## Hermes Kanban remains the sole execution authority

This project MUST NOT become a second state machine controlling Hermes work.

Native Hermes continues to own:

```text
task identity
task status
claims
workers
dependencies
review
blocking
completion
retry/recovery
run history
task events
workspaces
delivery metadata
```

The outcome layer owns only:

```text
objective
expected observable outcome
observation criteria
observation timing
observation evidence
outcome assessment
```

An outcome status is **derived project knowledge**, not a Kanban lifecycle status.

For example:

```text
Kanban status: done
Outcome state: awaiting_observation
```

is valid.

The outcome layer MUST NEVER change `done` back to another Kanban state because an outcome later fails.

A failed outcome creates information or follow-up work; it does not rewrite delivery history.

---

# 3. Non-Negotiable Invariants

The implementation must preserve these invariants.

### I. No direct Kanban database writes

Do not directly modify:

```text
kanban.db
tasks
task_runs
task_events
claims
links
```

Do not import private Hermes internals to bypass native lifecycle APIs.

All interaction with Kanban must use supported Hermes tools/interfaces.

### II. No competing lifecycle transitions

The extension must never directly:

- mark a task complete;
- approve review;
- request changes;
- block/unblock a delivery task;
- clear a claim;
- reassign a running task;
- advance integration state.

### III. Completed delivery history stays immutable

Outcome observation occurs **after** the canonical delivery record.

A later observation may conclude:

```text
confirmed
partially_confirmed
not_confirmed
regressed
inconclusive
```

but none of those conclusions alters the historical fact that Hermes completed the delivery task.

### IV. Fail observationally

If the plugin crashes, is disabled, or cannot parse outcome metadata:

**normal Hermes execution must continue unaffected.**

Outcome functionality is additive.

### V. No hidden second truth

For MVP, prefer native durable Hermes records over a separate plugin database.

If caching/indexing is eventually added, it must be completely reconstructible from canonical Hermes records and must never become authoritative.

### VI. Evidence over agent assertion

An agent saying “this worked” is not sufficient.

Outcome observations should contain the evidence used to reach the conclusion.

Pointers and summaries are preferred over dumping raw logs, secrets, transcripts, credentials, or sensitive content into Kanban.

---

# 4. Conceptual Model

The basic object is an **Outcome Contract** attached to a durable delivery-root Kanban card.

```text
Delivery Root
│
├── Objective
│
├── Expected Outcome
│
├── Observation Criteria
│
├── Observation Timing
│
└── Delivery work
       │
       ▼
   native Kanban
       │
       ▼
      DONE
       │
       ▼
   Observation
       │
       ├── confirmed
       ├── partially_confirmed
       ├── not_confirmed
       ├── regressed
       └── inconclusive
```

## Objective

Why are we doing the work?

Example:

> Make Agile iterations a usable first-class capability for an Odoo Project without changing normal Project task semantics.

## Expected Outcome

What should become observably true if the delivery succeeds?

Example:

> A configured Odoo Project can create a sprint, assign existing project tasks to it, close the sprint, and report the resulting sprint state.

## Observation Criteria

What evidence would support or contradict that outcome?

Example:

```text
- module installs cleanly on Odoo 19
- project can enable Agile behavior
- sprint can be created
- existing tasks can be assigned
- sprint can close
- resulting state can be queried/reported
- non-Agile projects continue behaving normally
```

## Observation Timing

When is observation meaningful?

Examples:

```text
immediate
after integration
after deployment
24 hours after deployment
after first real workflow
after one scheduled cycle
manual
```

The MVP should record this requirement without inventing its own scheduler.

---

# 5. Native Storage Strategy

## MVP: no independent outcome database

Outcome information should initially live in the native Kanban task thread.

Use durable, structured comments attached to the delivery-root card.

Example contract:

```text
[hermes-outcome:v1]
type: contract
id: oc_01
objective: Make Agile iterations usable for an Odoo Project.
expected_outcome: A project can create, populate, close, and report on a sprint.
observe_when: after_integration
criteria:
  - module installs on Odoo 19
  - sprint can be created
  - existing tasks can be assigned
  - sprint can be closed
  - sprint results can be queried
created_by: faolan
```

Example observation:

```text
[hermes-outcome:v1]
type: observation
contract_id: oc_01
result: confirmed
summary: Sprint workflow completed successfully in the integration environment.
evidence:
  - Odoo test suite: 47 passed
  - manual workflow: create → assign → close → report
residual_risk:
  - not yet observed with a production-sized project
observed_by: gilfoyle
```

The exact serialization format may be JSON or another deterministic encoding if that makes parsing safer.

Requirements:

- explicit version marker;
- deterministic schema;
- easy human readability;
- easy machine parsing;
- append-only history;
- duplicate detection by stable contract/observation IDs.

Do not silently overwrite earlier observations.

---

# 6. Derived Outcome States

The extension may present a derived state:

```text
untracked
planned
delivered
awaiting_observation
confirmed
partially_confirmed
not_confirmed
regressed
inconclusive
```

These are **not Kanban statuses**.

They must be reconstructed from:

```text
native task status/events
+
outcome contract records
+
outcome observation records
```

For example:

```text
contract exists + task open
    → planned

contract exists + task done + no observation
    → awaiting_observation

latest valid observation = confirmed
    → confirmed
```

Avoid adding an elaborate state machine unless actual use demonstrates a need for one.

---

# 7. MVP Plugin Surface

Keep the initial tool surface small.

## `outcome_define`

Attach an outcome contract to an existing durable delivery-root task.

Inputs should include:

```text
task_id
objective
expected_outcome
criteria[]
observe_when
optional notes
```

Behavior:

1. Read the target through native Kanban.
2. Check for an existing active contract.
3. Append a structured contract using `kanban_comment`.
4. Do not change the card's lifecycle state.

Repeated identical requests should be idempotent.

---

## `outcome_show`

Show the outcome contract and observation history for a delivery root.

Return:

```text
task
kanban_status
objective
expected_outcome
criteria
observation_timing
derived_outcome_state
observations
latest_evidence
residual_risk
```

Read only.

---

## `outcome_observe`

Record a post-delivery observation.

Inputs:

```text
task_id
result
summary
evidence[]
residual_risk[]
```

Rules:

- normally require the delivery task to already be `done`;
- never alter its status;
- append observation through native `kanban_comment`;
- retain previous observations;
- support later regression observations.

If the task is not done, fail closed unless an explicit future requirement demonstrates a legitimate pre-delivery observation use case.

---

## `outcome_check`

Evaluate whether an outcome needs attention.

Examples:

```text
awaiting observation
observation overdue
latest observation inconclusive
outcome not confirmed
previously confirmed outcome later regressed
```

Initially this may operate on one supplied task ID.

Do not build an expensive fleet-wide crawler for MVP.

---

# 8. Kanban Integration

Use Hermes's public plugin APIs.

The implementation may subscribe to:

```text
kanban_task_completed
```

The hook is informational only.

Because Hermes fires lifecycle observers after the Kanban state change commits, the plugin may use the completion event to recognize:

> The linked delivery is now canonically complete.

The hook MUST NOT reinterpret or replace the completion decision.

Possible MVP behavior:

```text
kanban task completes
       │
       ▼
does task contain an outcome contract?
       │
       ├── no → NO_ACTION_REQUIRED
       │
       └── yes
             │
             ▼
        outcome is now
        awaiting observation
```

Do not automatically create new work merely because a delivery finished.

Preserve `NO_ACTION_REQUIRED` as a valid result.

---

# 9. Follow-Up Work

If an observation discovers a problem:

```text
DELIVERED
    ↓
OBSERVED
    ↓
NOT CONFIRMED
```

the extension should not reopen the completed delivery card.

Instead, it may **suggest** creation of a new native Kanban child/follow-up card.

Example:

```text
t_original_delivery [done]
        │
        └── t_followup [ready]
            "Investigate failed sprint-close observation"
```

For MVP, follow-up creation should require an explicit agent or human action.

Possible later enhancement:

```text
outcome_observe(..., create_followup=true)
```

If implemented, creation must go through native `kanban_create` / `kanban_link` semantics.

Never create hidden plugin-owned work items.

---

# 10. Scheduling

Do not build a scheduler.

An Outcome Contract may record:

```text
observe_when
observe_after
```

but scheduling should eventually use existing Hermes capabilities such as cron if automation is necessary.

Phase 1 may rely on Faolan/human invocation of `outcome_check`.

A later phase may implement a small native-Hermes cron workflow that identifies specifically declared due observations.

Do not poll continuously.

---

# 11. Agent Workflow

A desired workflow looks like this.

### Planning

Faolan creates or identifies a durable delivery root and defines:

```text
objective
expected outcome
observation criteria
observation timing
```

### Execution

Existing Hermes workflow proceeds unchanged:

```text
decomposition
implementation
review
verification
integration
delivery enforcement
kanban completion
```

### Delivery

Native Kanban records `done`.

The outcome layer derives:

```text
awaiting_observation
```

### Observation

At the appropriate time, Faolan, Gilfoyle, Elara, another appropriate profile, or a human performs the declared checks and calls:

```text
outcome_observe
```

### Result

If confirmed:

```text
NO_ACTION_REQUIRED
```

If not confirmed:

```text
record evidence
surface the gap
optionally create normal Kanban follow-up work
```

---

# 12. Example

Delivery root:

```text
Implement Package double-move protection in Barcode workflow
```

Outcome Contract:

```text
Objective:
Prevent users from moving the same package A → B twice and
causing negative stock at Location A.

Expected outcome:
Once package P has been moved from A to B, a second attempt
to execute the same A → B movement is rejected or safely
reconciled before stock at A becomes negative.

Observation criteria:
- first package movement succeeds
- package location becomes B
- repeated scan cannot consume stock from A again
- no negative quantity is created at A
- legitimate subsequent movement B → C still works

Observe:
integration test + one real Barcode workflow
```

Hermes then performs the normal implementation/review/delivery workflow.

After delivery:

```text
Observation: confirmed

Evidence:
- automated package-move regression tests pass
- manual Barcode sequence A → B succeeds
- repeated A → B attempt is rejected
- B → C remains valid

Residual risk:
- concurrency behavior with two scanners has not yet been load tested
```

The original implementation task remains `done`.

No secondary task state exists.

---

# 13. Explicit Non-Goals

Do NOT build these as part of this project:

```text
org chart
agent hierarchy
budgets
mission portfolio
initiative engine
autonomy levels
agent hiring
general project-management dashboard
replacement Kanban board
custom worker dispatcher
custom review system
custom scheduler
duplicate task database
delivery state machine
automatic remediation engine
Paperclip clone
Project Stewardship clone
```

Avoid scope creep.

---

# 14. Security / Data Handling

Outcome evidence can contain project-sensitive information.

Requirements:

- never store credentials or API keys;
- do not dump full session transcripts;
- do not store arbitrary file contents by default;
- do not automatically ingest repository files as evidence;
- prefer concise evidence summaries and pointers;
- respect Hermes's existing redaction mechanisms;
- treat dashboard exposure as the same security boundary as the Kanban data it displays.

No transcript aggregation is required.

---

# 15. Dashboard

A dashboard is **not required for MVP**.

Start with:

```text
plugin tools
+
optional CLI/slash command
+
Kanban comments
+
observer hook
```

Only add dashboard UI after the workflow has proven useful.

A future lightweight Kanban augmentation could show:

```text
Outcome: Awaiting observation
Outcome: Confirmed
Outcome: Not confirmed
```

and render the contract/observation history.

It must derive those views from canonical records rather than own them.

---

# 16. Phase 0 — Reconnaissance

Before implementation, confirm the current Hermes public interfaces needed by the design.

Specifically verify:

1. `kanban_comment` can append to completed cards.
2. `kanban_show` exposes the full comment history required for deterministic reconstruction.
3. plugin hooks can call `ctx.dispatch_tool()` inside Kanban worker/headless contexts.
4. `kanban_task_completed` fires only after canonical completion commits.
5. no private `kanban_db` calls are required for any MVP operation.
6. comment size limits and redaction behavior are acceptable.
7. repeated reads/parsing of one task thread are cheap enough for interactive use.
8. plugin failure cannot interfere with normal Kanban completion.

If any assumption is false, stop and document the smallest necessary design adjustment rather than reaching into private Hermes internals.

---

# 17. MVP Acceptance Criteria

The project is successful when all of the following are true:

### Functional

A user or Hermes profile can:

```text
define an outcome contract
view it
complete the associated task through normal Hermes
record a post-delivery observation
view the resulting derived outcome state
record a later regression observation
```

### Authority

Tests prove the plugin cannot independently:

```text
complete a task
approve review
clear a claim
alter dispatcher state
rewrite task events
change canonical run history
```

### Persistence

Restarting Hermes preserves all outcome information because the authoritative records are native durable Kanban records.

### Multi-profile consistency

Faolan, k3rn3l, Gilfoyle, and other profiles looking at the same Kanban board must observe the same outcome history.

There must not be separate per-profile outcome realities.

### Failure isolation

Disable or intentionally break the plugin and prove that normal Kanban execution, review, and completion continue to work.

### Idempotency

Retrying contract creation or replaying lifecycle hooks must not produce duplicate logical contracts or contradictory synthetic state.

### Provenance

Every observation records:

```text
who/which profile observed it
when
result
summary
evidence
residual risk
```

---

# 18. Testing Strategy

Include tests for at least:

```text
contract creation
contract parsing
duplicate contract detection
malformed contract handling
task completion before observation
observation against unfinished task
confirmed outcome
partial outcome
failed outcome
regression after confirmation
multiple observations
plugin restart
multiple profiles reading same task
duplicate hook delivery
hook exception isolation
redaction-sensitive evidence
follow-up suggestion
NO_ACTION_REQUIRED path
```

Add an integration test against a disposable real Hermes board.

The integration test must prove that native `task_events`, `task_runs`, review state, and completion history remain exactly what Hermes itself produces.

---

# 19. Architecture Constraint Test

Before merging, answer this question for every persistence/write path:

> If this plugin disappeared tomorrow, would Hermes still know exactly what work happened and whether the delivery task completed?

If the answer is **no**, the design has taken ownership of something it should not own.

For outcome-specific data, ask:

> Can the outcome history be reconstructed from native durable Hermes records without consulting hidden plugin state?

For MVP, the answer should be **yes**.

---

# 20. Deliverables

Produce:

1. a short architectural decision record confirming the native-record design;
2. Phase-0 findings against the installed/current Hermes version;
3. plugin implementation;
4. schemas for Outcome Contract and Observation records;
5. unit tests;
6. disposable-board integration tests;
7. concise README with workflow examples;
8. threat/failure analysis focused on authority boundaries;
9. demonstration using one real low-risk project.

Do not implement dashboard UI until the CLI/tool workflow has been exercised successfully.

---

# 21. Pilot

Pilot on one low-risk repository/project.

Suggested process:

```text
choose one real delivery root
        ↓
define outcome contract
        ↓
run normal Hermes workflow
        ↓
deliver normally
        ↓
perform declared observation
        ↓
record result
        ↓
evaluate whether the extra semantics were useful
```

The pilot should answer:

- Did defining the expected outcome improve the work specification?
- Was post-delivery observation meaningfully different from ordinary verification?
- Did agents understand the distinction between delivery and outcome?
- Did it create useful follow-up work?
- Was the additional bookkeeping small enough to justify keeping?
- Which parts should remain convention rather than code?

Only expand the project if the pilot demonstrates real value.

---

# North Star

The project should make this statement possible:

> **Hermes proved that we delivered what we said we would deliver. The Outcome Loop helped us determine whether delivering it actually accomplished what we wanted.**

Do that without weakening, duplicating, or competing with Hermes Kanban.