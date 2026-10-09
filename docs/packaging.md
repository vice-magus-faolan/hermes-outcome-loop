# Packaging and installation

SPDX-License-Identifier: GPL-3.0-or-later

## Artifact and prerequisites

This is a native Hermes **directory plugin**, not a pip entry-point package.
The root contains `plugin.yaml` v2 and `__init__.py`; its relative package and
three fixed JSON schemas are shipped together. `register(ctx)` exposes exactly
four tools in toolset `outcome`, without a completion hook or privileged override.
The two direct runtime dependencies are `jsonschema==4.25.1` and
`referencing==0.37.0`. Their transitive dependencies are resolved by Hermes PM,
not vendored or manually pip-installed into an immutable runtime.

Compatibility is demonstrated against Hermes source
`f42f579cf8bac4918ac9599bece71618afadd846` on Linux/Python 3.14. Other revisions
and operating systems are unverified. Require supported `PluginContext`
registration/dispatch, explicit native board routing, complete comment history
and native install/PM admission. Do not infer compatibility merely from version
numbers. The four tools need an existing durable root and access to its board.

Build the portable artifact with `python3 scripts/package_plugin.py` (stdlib
only). It refuses an existing output directory; choose a new `--output` for a
second build. The output contains a directory and deterministic tarball,
excluding tests, Docker, Git/runtime state and credentials. A tarball is transport,
not a new Hermes installer; extraction must retain the complete directory layout.
Git source installs remain supported by the native installer. Independent final
review and publication are separate gates; a built artifact is not live deployment.

## Operator-only future installation

These are instructions, not permission to install into a live profile. Select the
intended profile explicitly. Review the exact source commit and native scan before
consenting to dependency preparation. In an approved environment:

```sh
hermes plugins install https://github.com/vice-magus-faolan/hermes-outcome-loop.git --ref FULL_REVIEWED_40_CHARACTER_SHA --no-enable
hermes plugins enable hermes-outcome-loop
hermes plugins list --user --json
hermes plugins doctor hermes-outcome-loop --ci
```

Replace the SHA placeholder with the actual independently reviewed commit. Native
installation scans the tree before publication. Caution requires supported consent;
dangerous findings must not be bypassed. No catalog membership or trust pin is
claimed. Dependencies require native PM consent/preparation. Non-interactive or
declined dependency preparation leaves the plugin disabled. `--enable` is not
permission to bypass dependency consent. Do not use `--force` to silence a scan,
edit `plugins.enabled` manually to evade admission, or pip-edit an immutable Hermes
environment. Hermes tools/configuration must enable toolset `outcome` for the
intended session; installed/enabled is distinct from session tool visibility.
Start a fresh session to pick up tools without changing a cached conversation.

## Rollback, removal and registration failure

Use `hermes plugins disable hermes-outcome-loop` first, then a fresh session.
This prevents subsequent plugin loading; it cannot cancel Python already running.
If no longer needed, use `hermes plugins remove hermes-outcome-loop` and read back
`hermes plugins list --user --json`. Never delete native Kanban data as uninstall
cleanup. Contracts/observations and all delivery provenance remain native comments,
events and runs. No plugin-specific database, daemon or migration needs rollback.
Dependency generations are owned by PM; leave their collection to supported PM
operations rather than deleting shared environments.

A missing schema/dependency or failed import/registration is a loader error, not
an outcome assessment. Inspect `plugins list`/`doctor`, disable the plugin, and
retain the error and exact source revision. Ordinary Kanban must remain usable.
Do not acknowledge tools as available just because cloning succeeded. Reinstall
an independently reviewed complete directory at its exact pin through the native
installer if files are missing. Do not repair Hermes core or a live runtime to
make a broken distribution import. A previously loaded process may retain old
handlers; use a fresh session rather than claiming removal instantly revokes code.

## Verification boundaries

`python3 scripts/verify.py` uses the existing restricted Docker environment for
schema/unit/architecture, Phase-0, production-native and mandatory packaging tests.
Public-only build provisioning acquires dependencies separately from network-denied
acceptance. Tests use disposable native homes/boards only, preserve supported scans
and consent, and compare exact pre-existing delivery history. Missing packaging
coverage/prerequisites fail, never skip. See README for the build/run commands and
[the threat model](threat-model.md) for what these checks cannot guarantee.
Remote CI runs this same canonical command; an unexecuted workflow is not green CI.

Offline admission reuses a complete dependency generation prepared through
supported `pm.sync_venv(Candidates(...), explicit=True)` in public provisioning.
The disposable identity is fixed inside container scratch because PM stamps
include installed member paths. The seed contains public cache/PM state only, not
plugin source or a pre-enabled profile. Acceptance restores it at the same
identity, installs the newly built artifact through native Git install, proves
non-interactive dependency consent is declined, then performs supported enable
and actual PM-selected environment activation. There are no registry shortcuts,
manual immutable-runtime pip edits, or upstream patches. PM does not forward
`UV_OFFLINE` during admission; an unseeded graph may require network and is not
claimed to work offline. Missing/incompatible seeds fail, never skip.
Public backend wheels are provisioned with PyPI digest checks. Supported native
`UV_NO_INDEX`/`UV_FIND_LINKS` settings prevent disable/removal from relying on
time-sensitive backend index caches; no PM command or consent is overridden.

Acceptance uses 1 GiB executable bounded scratch tmpfs for the writable cache and
dependency generations, retaining 2 GiB RAM/no extra swap and all other candidate
restrictions. Only build-provisioned tool payloads are linked read-only; native
locks, selection, cache and generations are writable inside disposable scratch.
Executability is needed for native PM, not permission for privileged containers.
Scratch is a test bound, not a production timeout or disk-fit guarantee. The
packaging gate proves four-tool/no-hook registration, definition/completion,
confirmation/stable retry/regression, fresh reconstruction, missing-schema loader
failure isolation, native disable/remove and exact native history preservation.

Local restricted-Docker canonical verification passed all 104 discovered tests,
including the complete native packaging gate. An earlier repeated run failed
during native disable when cached backend index metadata expired; that failure
is retained in native run evidence, not treated as a pass. The public wheelhouse
fix removes this cache-age dependency. Independent exact-artifact review and
remote CI remain separate obligations; no live installation was performed.
