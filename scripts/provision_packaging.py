#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the exact disposable plugin dependency identity using supported PM.

Native selection reuses a complete PM generation offline. Fresh selection without
this seed requires network: PM does not forward UV_OFFLINE during plugin admission.
Nothing in this script is shipped in the plugin or run against a live home.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib
from urllib.request import urlopen

from packaging.requirements import Requirement
from packaging.version import Version

BASE = Path("/scratch/outcome-phase0-native-packaging")
if os.environ.get("OUTCOME_DOCKER_PROVISION") != "f42f579cf8bac4918ac9599bece71618afadd846":
    raise RuntimeError("container public provisioning only")
home = BASE / "host-home/.hermes"
profile = home / "profiles/phase0-a"
plugin = profile / "plugins/hermes-outcome-loop"
plugin.mkdir(parents=True)
shutil.copyfile("/provision/plugin/plugin.yaml", plugin / "plugin.yaml")
(profile / "config.yaml").write_text("plugins:\n  enabled: []\n")
tools = home / "tools"
tools.mkdir()
for entry in Path("/provision/home/tools").iterdir():
    if entry.is_dir():
        (tools / entry.name).symlink_to(entry, target_is_directory=True)
    elif entry.name == "facts.json":
        shutil.copyfile(entry, tools / entry.name)
cache = home / "cache/uv"
cache.parent.mkdir()
shutil.copytree("/provision/cache", cache, copy_function=os.link)
os.environ.update(HOME=str(BASE / "host-home"), HERMES_HOME=str(profile),
                  HERMES_RUNTIME_DIR=str(tools), HERMES_PROFILE="phase0-a")
sys.path.insert(0, "/opt/hermes")
import pm
from pm.plugin_inputs import Candidates
pm.sync_venv(plugins=Candidates([plugin]), explicit=True)
# PM's supported index knobs keep backend resolution independent of HTTP cache age.
# Fetch public wheel bytes only; do not pip-edit any managed runtime.
wheelhouse = Path("/provision/packaging-wheelhouse")
wheelhouse.mkdir()
requirements = tomllib.loads(Path("/opt/hermes/pyproject.toml").read_text())["build-system"]["requires"]
for text in [*requirements, "packaging"]:
    requirement = Requirement(text)
    with urlopen(f"https://pypi.org/pypi/{requirement.name}/json", timeout=60) as response:
        metadata = json.load(response)
    versions = [Version(value) for value in metadata["releases"]
                if not Version(value).is_prerelease and Version(value) in requirement.specifier]
    version = str(max(versions))
    wheel = next(row for row in metadata["releases"][version]
                 if row["filename"].endswith("none-any.whl") and not row.get("yanked"))
    if not wheel["url"].startswith("https://files.pythonhosted.org/"):
        raise RuntimeError("public backend wheel origin mismatch")
    with urlopen(wheel["url"], timeout=60) as response:
        body = response.read()
    if hashlib.sha256(body).hexdigest() != wheel["digests"]["sha256"]:
        raise RuntimeError("public backend wheel digest mismatch")
    (wheelhouse / Path(wheel["filename"]).name).write_bytes(body)
seed = Path("/provision/packaging-seed")
seed.mkdir()
for name in ("cache", "installs", "tools"):
    shutil.move(str(home / name), seed / name)
# All seed bytes came from public source/dependency provisioning, never credentials.
for path in seed.rglob("*"):
    if not path.is_symlink():
        path.chmod(0o755 if path.is_dir() else 0o644)
shutil.rmtree(BASE)
print("Public packaging seed prepared through PM", flush=True)
