# Acceptance-to-test map

The normative machine-readable map is
[`tests/fixtures/outcome/acceptance-map.json`](../tests/fixtures/outcome/acceptance-map.json).
It covers every named ADR boundary with existing schema/oracle tests AND explicit
mandatory downstream production gates. `test_complete_acceptance_mapping_names_existing_tests`
checks completeness and real test names; prose-only promises do not count as tests.

Current executable specification:

- `schemas/*.schema.json`: closed Draft 2020-12 shapes; `schemas/protocol.json`:
  explicit application limits, authority/scope decisions and acceptance boundaries.
- `tests/fixtures/outcome/golden.json`: immutable contract, each of five observation
  results, comparable confirmed-to-regressed chain and two-criterion partial case.
- `negative.json`: shape/version/provenance-spoofing/date/blank/evidence/pointer failures.
- `histories.json`: state/action matrix, logical retries, contract/observation conflicts,
  multiple contracts, concurrent forks/roots, missing predecessors, cycles, orphan
  and cross-target histories, unfinished status, invalid regression/artifact/baseline.
  Mixed conflict/edge/evidence cases exercise all-variant diagnostic union, not just
  summary-only conflicts; every invalid-history fixture is tested under permutations.
- `native-responses.json`: malformed ordinary/marked native rows, missing/invalid
  body/author/time, null/nonobject rows and lone-surrogate UTF-8 failures. Tests mix
  these with valid histories, reject writes and exclude rejected rows from views.
- `uri-admission.json`: hierarchical/non-hierarchical rejected URI forms applied to
  every free-text field, including nested baselines, plus ordinary prose/UTC/clock
  and safe HTTPS controls. Evidence/baseline pointer fields reject these forms too.
- `scripts/outcome_spec.py`: bounded, test-only data oracle; no plugin registration,
  native dispatch, evidence I/O or persistence. Closed schema registry never fetches.
- `tests/test_outcome_spec.py`: schema checks, byte-boundary/strict-JSON tests,
  all permutations of a tied-time chain, occurrence retention, diagnostic precedence,
  preflight retry/stale-head/fence policy, due-time truthfulness and redacted readback.
  Golden payload checksums and a changed-meaning regression make corruption visible
  after restart without a hidden copy of the original request.

Focused command:

```sh
python3 -m unittest discover -s tests -p test_outcome_spec.py -v
```

Canonical command remains `python3 scripts/verify.py`, now through the restricted
Docker runner with an explicit pre-provisioned image content ID. See the
[Docker source handoff](docker-integration.md); construction and current native
acceptance remain blocked, not silently skipped. Repo-local schema/unit venvs do
not substitute for native Docker checks. Missing schema dependency is an error.
Historical Phase-0 prerequisites/results are preserved in the findings, but are
not the current host-side execution path. Schema meta/format validation remains
offline; ordinary verification does not fetch docs or evidence.

The specification milestone's architecture checks constrain the oracle's
imports/effects and the explicit tool/scope allowlist. They did not test the then
absent production adapter. Production must independently exercise
its own parser/adapter against these fixtures, statically AND dynamically constrain
all native calls to show/comment, and exercise actual registration/native persistence,
status/fence/read-write-readback failures, concurrent races and disabled/error plugin
completion. The real disposable integration lane owns whole native-history comparison,
restart and multi-profile proof for the production plugin. Existing Phase-0 tests are
feasibility evidence, not substitutes for those production gates.

The [core implementation](core-implementation.md) now has separate production
unit/architecture coverage in `tests/test_outcome_core.py`, `test_outcome_adapter.py`,
`test_outcome_boundaries.py` and `test_outcome_verification.py`. The closed
[`production-map.json`](../tests/fixtures/outcome/production-map.json) maps every ADR
boundary to actual test IDs. Canonical verification requires every named gate to
be discovered; removing one fails closed. These tests exercise the production
parser/adapter, not the oracle. Simultaneous fake-transport race tests are explicitly
unit evidence, never production native integration or persisted native API results.
Whole-history preservation, production restart/multi-profile/disabled behavior and
supported packaging remain mandatory downstream gates.

New mandatory `test_native.ProductionNativeTests` discovery covers real scoped
public registration/dispatch, all results and regression, unfinished/retry rejection,
full native history preservation, fresh profile/process reconstruction, actual
parallel races and failure/admission/readback cases. The runner's own policy tests
are separate from native evidence. These new native gates are UNEXERCISED pending
budget-admitted construction; their discovery is not a successful run. Supported
distribution plugin admission/consent remains downstream, not bypassed by the
source-loader integration fixture.

Production timing additionally requires `test_outcome_timing.py` through the same
machine-readable map: both reviewed overflow reproducers, define/readback/retry
readability, earlier explicit deadlines, all supported anchor sources,
zero/maximum delays, last-second and full-year-range controls. The separate
`derived_due_out_of_range` diagnostic must not become an invalid-history error or
an invented timestamp. The specification has its own elapsed-duration full-range
regression; it is not substituted for these production tests.

No capability-level isolation claim: Python is not sandboxed. No automatic follow-up,
hook, scheduler, fleet crawler, database or evidence ingestion may be introduced just
to satisfy a test. Assertions about native persistence must use actual native reads;
test-oracle output is never presented as a native API result.

## Specification builder verification evidence (historical)

- Original proposed artifact: focused 21 tests and canonical 42 tests passed, but
  independent review found three gaps. Passing that narrower suite was insufficient.
- Remediation specification suite: 24 tests pass, including golden schemas, negative
  shapes, mixed-conflict permutations and occurrence retention, recursive URI
  admission, malformed native responses, byte boundary and canonical checksum.
- Remediation canonical suite: 45 tests pass, including mandatory real-runtime Phase-0 probes.
- RED/GREEN: the invalid-date fixture initially failed because a bare schema
  format annotation lacked an installed optional checker; explicit UTC calendar
  validation restores GREEN. A controlled checksum-check bypass makes the
  changed-meaning regression fail; restoring integrity validation restores GREEN.
  No temporary mutation is part of the artifact.
- Review remediation RED/GREEN: new mixed-conflict/native-response/URI fixtures fail
  against the previous oracle (wrong diagnostics, accepted URIs, false clean states
  and uncaught attribute/Unicode errors). All pass after all-variant reconstruction,
  scheme-token admission and staged native validation. Nonstring/unencodable stored
  readback remains `write_unverified`; malformed provenance does not bypass byte caps.
- Removing Phase-0 runtime prerequisites makes canonical verification fail with
  the required-runtime error, not skip. Running without site packages makes it
  fail on the missing schema dependency, not silently accept unchecked schemas.
- Conservative complexity audit maximum is 15. The oracle's graph/evidence/
  preflight/reconstruction functions exceed the soft warning of 10: they deliberately
  aggregate boundary diagnostics, exercised by golden/negative histories and
  permutations; none exceeds 15. Grouping, native validation and regression checks
  are separate small functions. This is a test oracle, not a
  justification for copying diagnostic monoliths into production.
- Source handoff and historical Phase-0 evidence are unchanged. No production
  plugin, remote CI, publication or live-installation success is claimed. The
  existing CI workflow still needs explicit runtime and dev-dependency provisioning
  in the downstream packaging/delivery lane; weakening canonical checks is not
  an alternative.
