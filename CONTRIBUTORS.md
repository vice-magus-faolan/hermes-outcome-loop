# Contributors and provenance

SPDX-License-Identifier: GPL-3.0-or-later

The repository's recorded Git author is Faolan
(`vice-magus-faolan@users.noreply.github.com`). Source was developed and reviewed
using the Faolan, k3rn3l and Gilfoyle agent profiles under operator direction.
Profile names describe the workflow roles, not additional human authors or legal
copyright claimants. Git history retains actual contributor attribution; native
review/run records retain independent artifact-review provenance.

No third-party implementation source is vendored into the plugin. Hermes is an
external runtime, not included in the distribution. Schema validation uses the
separately declared `jsonschema` and `referencing` dependencies and their own
licenses. The test image acquires pinned public Hermes source and dependencies;
it is a verification environment, not the plugin release artifact.
