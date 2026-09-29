"""The deployment image is built before a release tag can be the first attempt."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> dict[str, Any]:
    path = ROOT / ".github" / "workflows" / name
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def _build_step(workflow: dict[str, Any], job: str) -> dict[str, Any]:
    steps = workflow["jobs"][job]["steps"]
    matches = [
        step for step in steps if step.get("uses", "").startswith("docker/build-push-action@")
    ]
    assert len(matches) == 1
    return matches[0]


def test_ci_builds_the_same_two_architectures_release_will_push() -> None:
    ci = _build_step(_workflow("ci.yml"), "container")["with"]
    release = _build_step(_workflow("release.yml"), "docker")["with"]

    assert ci["context"] == release["context"] == "."
    assert ci["platforms"] == release["platforms"] == "linux/amd64,linux/arm64"
    assert ci["push"] == "false"
    assert release["push"] == "true"


def test_the_on_demand_local_target_builds_the_same_dockerfile() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^image:.*\n((?:\t.*\n)+)", makefile, re.MULTILINE)
    assert match is not None
    assert "docker build --tag alleleforge-ci ." in match.group(1)
