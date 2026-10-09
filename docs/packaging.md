# Packaging and installation

This is a Hermes **directory plugin**, not a pip entry-point package. Ship the
root `plugin.yaml`, `__init__.py`, relative `hermes_outcome_loop` package and fixed
JSON schemas together. Registration exposes four tools in toolset `outcome`,
with no hook or privileged override. Runtime dependencies are declared in the
manifest: `jsonschema==4.25.1` and `referencing==0.37.0`.

The native integration tests target Hermes revision
`f42f579cf8bac4918ac9599bece71618afadd846` on Linux/Python 3.14. Other revisions and
operating systems are unverified. Test source registration is distinct from live
installation, dependency admission and tool visibility in an existing session.

## Build

```sh
python3 scripts/package_plugin.py --output dist
```

The output is a portable directory and reproducible tarball. Existing output
paths, missing inputs and symlinked inputs are rejected. Tests, Docker, Git state
and credentials are excluded. A tarball is transport, not a separate installer.

## Install in an explicitly chosen profile

Use the native installer with an exact reviewed commit; these instructions do
not authorize an assistant to change a live profile:

```sh
hermes plugins install https://github.com/vice-magus-faolan/hermes-outcome-loop.git --ref FULL_REVIEWED_40_CHARACTER_SHA --no-enable
hermes plugins enable hermes-outcome-loop
hermes plugins list --user --json
hermes plugins doctor hermes-outcome-loop --ci
```

Review native scan findings and dependency consent. Do not use `--force` to
silence warnings, edit enablement to evade admission, or manually patch a shared
Hermes dependency environment. Enable toolset `outcome` for the intended session;
start a fresh session for newly available tools. The plugin needs access to the
explicitly selected native board and existing task.

## Disable, remove or recover

Use `hermes plugins disable hermes-outcome-loop`, then a fresh session. If no
longer needed, use `hermes plugins remove hermes-outcome-loop` and read back the
plugin list. Never delete native board data: outcome comments, delivery events
and runs remain canonical. There is no plugin-specific database or migration.

Missing schemas/dependencies or failed registration are loader errors, not outcome
assessments. Inspect `plugins list`/`doctor`, disable the plugin and preserve the
error/revision. Recover through native installation of a complete reviewed
artifact, not a Hermes core patch. Already loaded Python cannot be revoked merely
by removing files; use a fresh session.

Repository tests cover archive reproducibility, source registration and actual
native outcome behavior. They do not test Hermes's package manager or promise
fully offline install/enable/remove. Native dependency preparation may need the
network. See [the threat model](threat-model.md).
