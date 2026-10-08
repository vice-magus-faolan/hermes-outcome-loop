# Docker native-integration source handoff

Status: runner mechanics exercised; construction and native integration NOT accepted.
The [Docker recovery decision](decisions/2026-10-08-docker-test-recovery.md)
governs this path. Historical native feasibility/core approvals and failed host
preparation are preserved; they are not retroactive container acceptance.

## Inputs and phases

- Hermes source: `f42f579cf8bac4918ac9599bece71618afadd846`, fetched from the public
  fork recorded in `scripts/provision_docker.py`. No live source or dependencies
  enter the image.
- Candidate base: Python 3.14.0 slim Bookworm, amd64 manifest
  `sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056`.
  Public registry manifest lookup resolved this pin; the base was NOT downloaded.
  This patch-level interpreter compatibility is untested, not an admission claim.
- OS package sources: Debian/Bookworm snapshot `20251119T000000Z`.
- Native dependencies: supported PM frozen export from the pinned Hermes lock,
  combined with the plugin's exact schema dependency declarations and built into
  a fresh environment. The candidate records the lock/requirements digests and
  actual installed distribution inventory. No pip mutation of a live or immutable
  environment is used. Provisioning and its dependency closure remain unexercised.
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

## Construction gate (currently closed)

`docker/build-budget.json` intentionally records unknown peaks and no measurement
receipt. Do not fill these with optimistic estimates or a boolean approval.
Before provisioning, the operator must choose a runner/storage arrangement and
review measured peaks or enforceable aggregate bounds for base compressed/unpacked
content, source checkout, dependency downloads/cache/runtime, intermediate layers,
build cache, final image, source/log/export space and simultaneous copies.
Discover the active Docker, containerd and builder stores, including daemon command
line/config overrides. A separate Docker data volume does not relocate containerd.

`docker_build_preflight.py` reports current storage and rejects unknown evidence,
mismatched source/base pins or inadequate reserves. It sums stores that share a
filesystem before enforcing the 2 GiB reserve. Evidence supplied to this helper
is trusted reviewed operator input, not independently established by an integer
in a JSON file. CI currently fails at this gate rather than allocating an unknown
peak. The runner's acceptance flags do not bound image construction disk usage.

After an actual budget is admitted, a provisioning sequence is:

```sh
# Substitute the DISCOVERED active containerd data root, not a guessed Docker path.
python3 scripts/docker_build_preflight.py --containerd-root /var/lib/containerd &&
  docker build --tag outcome-integration:local --file docker/Dockerfile .
```

This recipe has not been built. A successful preflight is not successful provisioning,
plugin admission or native acceptance. A future builder must verify all three.

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

## Authored production-native cases (unexercised)

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

## Real results from this source continuation

- Existing outcome focused suite: 66 tests passed (unchanged production source).
- Runner smoke in an existing Python image: eight runner-policy tests passed;
  engine-limit readback and exact owned-container cleanup passed. This image is
  NOT the Hermes candidate and is not native integration evidence.
- New fixture path/environment safety test passed without importing Hermes.
- Complexity audit includes the new runner/native/provisioning code; no function
  exceeds 15. The fault dispatch and engine readback boundary each soft-warn at 11.
- Canonical host verification fails explicitly without `HERMES_OUTCOME_IMAGE`;
  attempted internal host entry fails the container fence. Retired host preparer
  exits unsuccessfully without effects. Construction preflight fails because
  measured/quota peak evidence is unknown.
- Native Docker construction, native integration, supported packaging and remote
  CI execution are NOT exercised. Required current acceptance is still red.

The two original failed integration runs and partial host output remain untouched.
The original preparer source was committed for recoverability before being replaced
by a non-operating retirement notice. No publication, integration-target change,
live plugin/profile/dependency change, service restart or pilot effect occurred.
Complete the existing card only after real required native checks and same-card
independent exact-artifact review; source preparation does not release successors.
