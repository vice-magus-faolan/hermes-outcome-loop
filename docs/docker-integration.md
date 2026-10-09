# Docker native-integration report

Status: pinned image construction and 101-test canonical native suite pass;
independent integration review and supported packaging remain pending.
The [Docker recovery decision](decisions/2026-10-08-docker-test-recovery.md)
governs this path. Historical native feasibility/core approvals and failed host
preparation are preserved; they are not retroactive container acceptance.

## Inputs and phases

- Hermes source: `f42f579cf8bac4918ac9599bece71618afadd846`, fetched from the public
  fork recorded in `scripts/provision_docker.py`. No live source or dependencies
  enter the image.
- Candidate base: Python 3.14.0 slim Bookworm, amd64 manifest
  `sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056`.
  Actual public-only Docker construction passed. PM selects its managed runtime
  interpreter from the pinned source, distinct from this build interpreter.
- OS package sources: Debian/Bookworm snapshot `20251119T000000Z`.
- Native dependencies: supported PM frozen export from the pinned Hermes lock,
  combined with the plugin's exact schema dependency declarations and built into
  a fresh environment. The candidate records the lock/requirements digests and
  actual installed distribution inventory. No pip mutation of a live or immutable
  environment is used. Actual provisioning and native imports passed.
- `.dockerignore` permits only the Docker recipe, frozen OS source declaration,
  provisioning script and schema requirements. It excludes host environments,
  partial preparation, profiles, credentials and the candidate worktree.

Public network acquisition belongs only to explicit image construction. Acceptance
uses an already-local literal image content ID, never an implicit pull or tag.
The source handoff is a bounded copy of Git-listed regular files (including dirty
source inputs), with symlink/runtime/credential-path rejection and a 16 MiB cap.
Only that disposable staging copy is mounted; the original worktree is not mounted.
A content digest plus source HEAD identify the actual staged candidate; HEAD alone
is not a claim that dirty source equals a committed artifact.

## Ordinary project provisioning

The operator's continuation supersedes the historical pre-build peak/quota gate.
`docker/build-budget.json` is retained as an unused historical input, not a live
admission requirement. Unknown peaks stay unknown. Confirm actual Docker and
containerd mount routing read-only; check accessible backing mounts rather than
root-owned data subdirectories. The small preflight checks the 2 GiB operational
reserve only. Neither it nor monitoring is a disk quota or a fit guarantee.

For the local run, Docker and containerd were confirmed to share one dedicated
mount. CI also checks the accessible root mount for default root-backed stores;
if runner storage routing changes, supply the actual accessible mounts through
repeatable `--store` arguments. No service/configuration changes are made.

```sh
# Default checks DockerRootDir and workspace; add --store for separate stores.
python3 scripts/docker_build_preflight.py
timeout --signal=TERM --kill-after=30s 1800s docker build --tag outcome-integration:local --file docker/Dockerfile .
```

The actual build exited 0. Capacity readbacks retained in native run metadata
include build cache and image-store activity, not a measured peak. The 2 GiB
reserve remained intact at readbacks. Runtime acceptance is separate
from public-only construction and must still pass on every candidate.

## Required acceptance

```sh
export HERMES_OUTCOME_IMAGE="$(docker image inspect outcome-integration:local --format '{{.Id}}')"
python3 scripts/verify.py
```

The canonical command runs the existing mandatory Phase-0 assertions AND the new
production-native assertions inside Docker. It fails without its image/runtime;
there is no native-skip or mock fallback. `--inside-docker` is an internal entry
point fenced to the non-root fixed container layout and read-only root/source.
That fence prevents accidental host execution; it is not a Python security sandbox.

The runner applies and reads back non-root UID/GID 65532, read-only root/source,
network `none`, dropped capabilities, no-new-privileges, two CPUs, 2 GiB RAM/no
extra swap, 256 PIDs and 512 MiB tmpfs. The container deadline is 20 minutes;
Docker logs have one 1 MiB uncompressed local file, exported output is bounded
at 2 MiB, and stdout receipts are compact. Loopback scripted provider traffic for
historical dispatcher tests remains inside the network-denied namespace. There
are no live-home/board/credential/socket mounts or host/privileged namespaces.

Exact owned container IDs/labels are checked before removal and absence is read
back afterward. Only owned containers and their source staging are removed; shared
images, volumes and global build caches are not pruned. Teardown errors cannot turn
a failed primary check into success, or hide its exit code. A successful primary
run with a teardown error still fails the runner.

## Exercised production-native cases

`tests/test_native.py` requires actual public PluginContext/registry dispatch from
`scripts/native_probe.py`, `native_runtime.py` and `native_cases.py`:

- define/show, unfinished rejection, explicit native builder review/reviewer
  completion, all five outcome results and a criterion-comparable regression;
- stable-ID retries with no write, fresh processes/two isolated profiles reading
  identical histories from the same explicit board;
- actual parallel profile processes forced to read the same predecessor before
  appending identical retries, conflicting same-ID payloads or sibling forks;
- full disposable read-only native snapshots comparing task, run, event, review
  and completion provenance; allow only the exact expected native comment additions;
- disabled plugin, malformed metadata, raised registered handler and read/write/
  readback fault injection while ordinary native review/completion still works;
- sensitive synthetic admission rejection, oversize rejection and actual stored
  native redaction/readback.

The test loader copies unchanged production source and its schemas into disposable
profile directories and uses normal public discovery/enablement. Only its fault shim
and race barrier are test behavior; native operations are real, not mocked. This
is source registration integration, NOT supported distribution install/scan/consent
or packaging acceptance. That remains the existing downstream packaging gate.
No native scan/consent routine is suppressed or patched. Any normal discovery or
registration rejection fails the native checks; it is not bypassed.

The production plugin has no completion hook. The new harness asserts no hook is
registered and derives results from fresh reads. Duplicate-hook/no-op and hook
exception cases therefore do not apply to production; the original Phase-0 observer
feasibility cases remain required unchanged. Python is not sandboxed; production
operations remain constrained by implementation/review, not capability isolation.
Read/append/read is non-atomic and does not promise physical exactly-once writes.
Evidence completeness does not establish evidence truth or universal secret detection.

## Actual execution and regression evidence

- Public-only pinned Docker build: exit 0; supported PM frozen export, fresh
  dependency construction, source-pin check and clean-source check succeeded.
- `python3 scripts/verify.py`: 101 tests passed, exit 0, in the restricted Docker
  environment. Includes all three production-native integration gates and the
  original real Phase-0 dispatcher/observer/history/scaling tests; no skip or mock
  substitute. Before/after disposable native snapshots passed exact comparisons
  of task/run/event/comment records, with only expected native comment additions.
- The first actual run failed on an incorrect `REDACTED` sentinel expectation.
  The pinned public writer stores a six-character head/four-character tail mask;
  the corrected test asserts that exact JSON value and stored/native history.
- Phase-0 failed to execute its scratch shell launcher on Docker's noexec tmpfs.
  It now uses the native running-interpreter module launcher; no tmpfs/security
  relaxation or native source change. A denied `/proc/.../environ` read also
  masked a primary error; cleanup now refuses unverifiable PID signalling while
  the exact owned container remains the final descendant-teardown boundary.
  Canonical regressions cover both fixes. Failed executions remain failed evidence.
- Complexity audit: no function exceeds 15. Soft warnings identify existing
  boundary/diagnostic functions, not permission for unreviewed complexity growth.
- Engine limits and exact owned-container removal/absence were verified after
  successful and failed acceptance runs. No test containers remain.
- Missing-image/runtime failures and host execution fences remain explicit.
  The CI source uses ordinary bounded provisioning and the same mandatory suite;
  remote CI, supported packaging/install/consent and publication are unexercised.

The two original failed integration runs and partial host output remain untouched.
The original preparer source was committed for recoverability before being replaced
by a non-operating retirement notice. No publication, integration-target change,
live plugin/profile/dependency change, service restart or pilot effect occurred.
Complete the existing card only after real required native checks and same-card
independent exact-artifact review; source preparation does not release successors.
