# MVP roadmap

Phase 0 has independent exact-artifact review. ADR/schemas are proposed for review;
production implementation and repository delivery remain pending.

1. **Phase 0 — public-interface feasibility.** Record installed Hermes version/full
   SHA, public API contracts and actual disposable-board probe results. Prove
   comment append after done, full deterministic history, plugin tool dispatch
   in headless/worker contexts, redaction/size behavior, lifecycle observer
   post-commit behavior/isolation and practical single-thread read cost.
2. **ADR and schemas.** Use Phase-0 findings to approve the native-record design,
   immutable contract/observation schemas, IDs/retries/concurrency, derived-state
   precedence, diagnostics, native provenance, board scope and timing rules.
   See the [ADR](decisions/2026-10-01-native-record-contract.md),
   [protocol](record-protocol.md) and [acceptance mapping](acceptance-tests.md).
3. **Core plugin and unit/architecture tests.** Implement four tools and a narrow
   native-tool adapter; no hook needed for correctness. Exercise every result,
   malformed history, redaction, duplicate/conflict, failed read/write/readback,
   unfinished-task rejection, suggested follow-up and NO_ACTION_REQUIRED.
4. **Disposable real-Hermes integration.** Exercise actual plugin registration,
   native completion/review provenance, restart, multiple isolated profiles,
   hook replay where applicable, exception/disabled-plugin paths, race/retry
   handling and preservation of pre-existing canonical history. Make required
   integration coverage part of the canonical verifier, not an optional claim.
5. **Packaging, docs and threat/failure analysis.** Supported plugin manifest and
   dependency admission; reproducible isolated install; concise exercised workflow
   examples; no live deployment. Canonical verification must cover all implemented
   surfaces and must not pass by silently skipping required integration checks.
6. **Reviewed delivery.** Converge the exact approved artifact, run canonical
   verification, publish through a green GitHub pull request and reconcile local
   `main` with the remote integration result. Preserve native review/run evidence.
7. **Approval-gated real-project pilot.** Choose a low-risk genuine delivery root,
   declare contract before delivery, observe afterward and evaluate usefulness.
   Operator approval of the pilot environment is required before live installation
   or real-project mutation. Report whether the bookkeeping was justified and
   what should remain convention rather than code. Expansion requires pilot evidence.

Ordinary work uses native same-card builder/reviewer/remediation lifecycle.
Implementation is serial and dependency-gated behind reviewed feasibility and schemas.
Do not expand into dashboards or operational automation during this milestone.
