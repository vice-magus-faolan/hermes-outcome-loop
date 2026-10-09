# Docker-based integration recovery

Status: operator-approved implementation direction, 2026-10-08.

Continuation amendment: the operator subsequently authorized ordinary bounded
local Docker builds and actual product tests, without a pre-build measured-peak
or quota approval. Docker is the test environment, not a separate deliverable.
The operational reserve and acceptance/effect boundaries below remain intact.

## Decision

Resume the existing integration component and serial feature lane. Run Hermes
acceptance environments in disposable Docker containers instead of constructing
additional Hermes installations or heavyweight dependency environments on the
host. Source editing and native project coordination remain unchanged.

This supersedes host-side runtime preparation as the preferred test path. It is
not production-native acceptance, publication, deployment or live installation
approval. Preserve original failed attempts and previously reviewed artifacts.

## Required boundaries

- Keep the test harness small and subordinate to outcome-plugin acceptance; do
  not build a general container platform or create a replacement task graph.
- Pin the actual Hermes source/version and image/dependency inputs. Use supported
  native plugin registration/admission and real Kanban operations, not mocks as
  substitutes for native acceptance. Do not alter Hermes source or bypass native
  plugin scans/consent to make unattended tests pass.
- Run all heavyweight native feasibility, integration, packaging/admission and
  historical re-attestation environments in Docker. Preserve test semantics and
  explicit missing-prerequisite failures; never silently skip native coverage.
- Prefer read-only source input or an explicitly bounded source archive. Exclude
  host virtual environments, partial preparation, runtime state and credentials
  from build contexts. Never mount live Hermes homes, boards, host credentials,
  the Docker socket or writable canonical source into acceptance containers.
- Candidate acceptance runs non-root with a read-only root filesystem, dropped
  capabilities, no-new-privileges, bounded memory/CPU/PIDs/time and explicitly
  sized temporary scratch. Use isolated container-local synthetic profiles and
  boards. Deny networking during acceptance; keep necessary public dependency
  acquisition in a separate, explicit provisioning phase. No privileged mode,
  host namespaces or daemon-security relaxation.
- Use finite log retention and bounded evidence exports. Keep primary failures
  even if evidence export or teardown fails. Record exact image/source identities,
  commands, exit codes, native readbacks and cleanup results. Do not infer native
  test success from a lightweight container smoke test.
- Use stable project-owned labels and names. Remove only owned test containers and
  explicitly identified disposable resources, checking exact identities before
  cleanup and absence afterward. No global image/volume/system prune, removal of
  shared base images, service restart, daemon migration or unrelated cleanup.

## Storage and failure boundary

Docker is isolation, not unlimited storage. Discover the actual Docker,
containerd and build-cache storage paths and their backing filesystems before
image acquisition or construction. A separate Docker data directory does not
necessarily relocate containerd image content/snapshots.

Check free space on the accessible actual backing mounts, not root-owned data
subdirectories, and retain the operational reserve. Ordinary finite-deadline
project builds and meaningful retries are authorized. Record observed usage
after execution; unknown peaks remain unknown and are not an admission blocker.
Neither resource flags nor monitoring constitute an aggregate disk quota or a
guaranteed fit. Diagnose concrete dependency/test failures on the same lane;
do not add an infrastructure prerequisite or helper-review chain.

Use initial acceptance ceilings of two CPUs, 2 GiB RAM with no extra swap,
256 PIDs, 512 MiB temporary scratch and a 20-minute deadline; changes require a
measured rationale. Preserve at least 2 GiB available on every filesystem used
for persistent construction and bounded evidence. These are conservative
operational limits, not a proven complete construction budget or fit guarantee.

## Retained partial work

Preserve interrupted host-side integration preparation and unfinished source
inputs as historical evidence. Do not restart it, copy it into images, reset the
feature lane or discard uncommitted source. Inventory exact inputs and adopt or
explicitly supersede them. Retiring the old partial runtime is not required to
resume source work and needs a separate verified, narrowly scoped cleanup step.

## Unchanged delivery obligations

Independent exact-artifact native review, full acceptance, cumulative packaging,
required CI and historical provenance re-attestation remain mandatory. Publication
and the real-project pilot remain separately gated. No target advancement,
profile changes, shared-host dependency changes or gateway restart is authorized.
