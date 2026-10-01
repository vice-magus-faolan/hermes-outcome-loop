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

Canonical command remains `python3 scripts/verify.py`. Use a repo-local venv with
`python3 -m pip install -r requirements-dev.txt`; do not modify Hermes/shared
packages. Missing schema dependency is an error, never a skipped check. Preserve the
explicit Phase-0 runtime prerequisites described in the findings. Schema meta/format
validation must be offline; ordinary verification must not fetch docs or evidence.

Architecture checks at this milestone constrain the executable specification's
imports/effects and the explicit tool/scope allowlist. They do NOT claim an absent
production adapter has been tested. Downstream must independently implement and test
its own parser/adapter against these fixtures, statically AND dynamically constrain
all native calls to show/comment, and exercise actual registration/native persistence,
status/fence/read-write-readback failures, concurrent races and disabled/error plugin
completion. The real disposable integration lane owns whole native-history comparison,
restart and multi-profile proof for the production plugin. Existing Phase-0 tests are
feasibility evidence, not substitutes for those production gates.

No capability-level isolation claim: Python is not sandboxed. No automatic follow-up,
hook, scheduler, fleet crawler, database or evidence ingestion may be introduced just
to satisfy a test. Assertions about native persistence must use actual native reads;
test-oracle output is never presented as a native API result.

## Builder verification evidence

- Focused specification suite: 21 tests pass, including golden schemas, negative
  shapes, invalid-history permutations, byte boundary and canonical checksum.
- Canonical suite: 42 tests pass, including mandatory real-runtime Phase-0 probes.
- RED/GREEN: the invalid-date fixture initially failed because a bare schema
  format annotation lacked an installed optional checker; explicit UTC calendar
  validation restores GREEN. A controlled checksum-check bypass makes the
  changed-meaning regression fail; restoring integrity validation restores GREEN.
  No temporary mutation is part of the artifact.
- Removing Phase-0 runtime prerequisites makes canonical verification fail with
  the required-runtime error, not skip. Running without site packages makes it
  fail on the missing schema dependency, not silently accept unchecked schemas.
- Conservative complexity audit maximum is 15. The oracle's grouping/evidence/
  contextual/preflight/reconstruction functions exceed the soft warning of 10:
  they deliberately aggregate boundary diagnostics, exercised by golden/negative
  histories and permutations; none exceeds 15. This is a test oracle, not a
  justification for copying diagnostic monoliths into production.
- Source handoff and historical Phase-0 evidence are unchanged. No production
  plugin, remote CI, publication or live-installation success is claimed. The
  existing CI workflow still needs explicit runtime and dev-dependency provisioning
  in the downstream packaging/delivery lane; weakening canonical checks is not
  an alternative.
