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


def _build_steps(workflow: dict[str, Any], job: str) -> list[dict[str, Any]]:
    steps = workflow["jobs"][job]["steps"]
    return [step for step in steps if step.get("uses", "").startswith("docker/build-push-action@")]


def _release_build_step(workflow: dict[str, Any], job: str) -> dict[str, Any]:
    matches = [
        step
        for step in _build_steps(workflow, job)
        if step["with"].get("platforms") == "linux/amd64,linux/arm64"
    ]
    assert len(matches) == 1
    return matches[0]


def test_ci_builds_the_same_two_architectures_release_will_push() -> None:
    ci = _release_build_step(_workflow("ci.yml"), "container")["with"]
    release = _release_build_step(_workflow("release.yml"), "docker")["with"]

    assert ci["context"] == release["context"] == "."
    assert ci["platforms"] == release["platforms"] == "linux/amd64,linux/arm64"
    assert ci["push"] == "false"
    assert release["push"] == "true"


def test_the_on_demand_local_target_builds_the_same_dockerfile() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^image:.*\n((?:\t.*\n)+)", makefile, re.MULTILINE)
    assert match is not None
    assert "docker build --tag alleleforge-ci ." in match.group(1)
    assert "docker run --rm --entrypoint python alleleforge-ci" in match.group(1)


def test_ci_boots_the_image_and_asks_the_service_if_it_is_healthy() -> None:
    job = _workflow("ci.yml")["jobs"]["container"]
    loadable = [
        step
        for step in _build_steps(_workflow("ci.yml"), "container")
        if step["with"].get("load") == "true"
    ]
    assert len(loadable) == 1
    assert loadable[0]["with"]["platforms"] == "linux/amd64"

    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "docker run --detach" in commands
    assert "--name alleleforge-ci-smoke alleleforge-ci:smoke" in commands
    assert "http://127.0.0.1:8000/api/health" in commands
    assert "body['status'] == 'ok'" in commands
    assert "os.getuid() == 10001 and os.getgid() == 10001" in commands

    cleanup = [step for step in job["steps"] if step.get("name") == "Remove smoke container"]
    assert len(cleanup) == 1
    assert cleanup[0]["if"] == "always()"
