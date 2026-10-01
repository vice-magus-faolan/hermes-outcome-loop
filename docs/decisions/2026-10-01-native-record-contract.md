# ADR: bounded native-record outcome contract

Date: 2026-10-01. Status: **Independently reviewed implementation contract.**
Acceptance of this ADR does not deliver a plugin.

## Context

[Reviewed Phase-0 evidence](../phase-0-findings.md) proves a guarded public
comment append/read path on the recorded Hermes installation. Native read-side
comment IDs are absent, timestamps tie, redaction can alter JSON, worker DB pins
can alias a mismatched board slug, and completion hooks misreport cross-board
identity. The [operator-approved ordering amendment](2026-10-01-record-ordering.md)
permits logical predecessor chains with visible ambiguity. The original handoff
and historical NO-GO evidence remain unchanged.

## Decision

1. Native Kanban owns all execution and delivery state. Native comments on one
   explicitly scoped delivery root are the only outcome authority. The production
   adapter calls only `kanban_show` and `kanban_comment` through public plugin
   dispatch; never SQL, private imports, CLI fallback or lifecycle tools.
2. One immutable v1 contract, followed by append-only v1 observations. Closed
   Draft 2020-12 [schemas](../../schemas/) plus the
   [record protocol](../record-protocol.md) define serialization and cross-record
   validation. Explicit stable contract IDs and observation IDs are caller-held
   retry identities, not time/order or author claims. No implicit identity hashes.
3. A unique predecessor chain determines the latest observation. Identical
   payload retries form one logical record but retain every native author/time
   occurrence. Conflicting IDs, multiple contracts, roots/forks, missing links,
   cycles, or any marked unreadable/unsupported record invalidate the derived
   assessment. No timestamp/position/native-ID/lexicographic winner or automatic
   reconciliation. Diagnose all payload variants via union edges and every matching
   contract/evidence variant, never a representative. Ancestry checks require an
   unambiguous complete chain. Idempotency is logical, not atomic insertion uniqueness.
4. Observation requires freshly read native `done`; any other status rejects it,
   including an identical retry. Criterion evidence, actual observation time,
   environment, conditional baseline and delivered artifact are explicit. Native
   author/time anchor attribution and persistence; caller authors are forbidden.
5. State precedence is invalid history, empty/untracked, unfinished/planned,
   done/awaiting observation, then the unique valid chain head's assessment.
   Delivery remains a separate native fact. Regression requires a supported
   criterion at a confirmed/partial ancestor and a new contradictory comparison.
6. Free-text timing never invents a due date. Only an explicit UTC deadline or
   known supported anchor plus delay yields `due`/`overdue`; otherwise due time is
   unknown. Check suggests attention/follow-up, never creates work or reopens a card.
7. Adopt application caps of 16,384 UTF-8 bytes per complete marked record,
   1,024 comments and 2,097,152 aggregate comment-body bytes per read history.
   Reject, never truncate. These match exercised Phase-0 bounds; they are not
   native limits or a bound on native read allocation. Schema field caps also apply.
8. Reject known sensitive inputs and unsafe pointers before dispatch, preserve
   native redaction, then freshly read the actual persisted record and whole
   history. Success needs byte-exact parsed readback and unambiguous history.
   Unknown commit/readback outcomes never mean rollback or success; no blind retry.
   A canonical payload checksum detects changed meaning on later reads without
   remembering the original request; it is not authentication or an identity hash.
   URI admission includes non-hierarchical schemes in every nested text field.
   Native row/body/author/time validation precedes ignoring unrelated comments;
   malformed input yields safe invalid-history diagnostics, not an exception or
   untracked result. Rejected native rows are never copied into occurrence views.
9. No completion hook, scheduler, crawler, database, persistent cache, automatic
   evidence ingestion, automatic follow-up or conflict resolver is required or
   included. Native execution remains independent when this plugin is absent.

## Verification and consequences

`python3 scripts/verify.py` includes schema metaschema/strict-JSON/golden/negative
checks, contextual fixture oracles, architecture constraints and the mandatory
real-runtime Phase-0 suite. [Acceptance mapping](../acceptance-tests.md) separates
this executable specification from production core unit/architecture checks and
required downstream native integration gates. The oracle remains test support,
not a registered plugin or proof of production native integration.

Concurrent writers can both append; post-write readback may precede a later race.
A successful response proves only the observed snapshot. Fresh reads expose later
forks. Conflicts remain visible and freeze further outcome writes; resolution or
contract replacement needs a separately approved future protocol. Manual attention
is preferable to a fabricated winner. Readback failure can leave a bad append
permanently present. Secret detection is bounded, not a guarantee against arbitrary
opaque/encoded secrets. Python plugins are not sandboxed; process exit, hostile
code, allocation exhaustion and nonterminating dispatch are not isolated.

Publication, installation, profile/shared-dependency changes, restarts, deployment
and pilot effects remain separately approval-gated. This ADR changes neither the
source handoff nor native task/review/completion semantics.
