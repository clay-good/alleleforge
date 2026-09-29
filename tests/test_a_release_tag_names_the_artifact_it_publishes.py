"""The release switch must identify the exact artifact it is allowed to publish.

The workflow described itself as tag-only while also exposing ``workflow_dispatch``, which
can run from an arbitrary branch. It then built and published whatever version happened to
be in that checkout without checking that the tag named it. A stray click or a mistyped tag
could therefore publish an artifact under a release that claimed to be another version.
"""

from __future__ import annotations

import os
import runpy
import shlex
import subprocess
from pathlib import Path

import yaml

_ROOT = Path(__file__).parents[1]
_WORKFLOW = _ROOT / ".github" / "workflows" / "release.yml"


def _release_workflow() -> dict[str, object]:
    # BaseLoader keeps YAML 1.1 from turning the key ``on`` into boolean True.
    loaded = yaml.load(_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def _version_guard() -> str:
    steps = _build_steps()
    guards = [step for step in steps if step.get("name") == "Verify tag matches package version"]
    assert len(guards) == 1
    return str(guards[0]["run"])


def _build_steps() -> list[dict[str, str]]:
    workflow = _release_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    build = jobs["build"]
    assert isinstance(build, dict)
    steps = build["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def test_a_release_can_only_start_from_a_version_tag() -> None:
    trigger = _release_workflow()["on"]
    assert trigger == {"push": {"tags": ["v*"]}}


def test_the_current_version_passes_the_release_guard() -> None:
    steps = _build_steps()
    guard_at = next(
        i
        for i, step in enumerate(steps)
        if step.get("name") == "Verify tag matches package version"
    )
    build_at = next(i for i, step in enumerate(steps) if step.get("run") == "python -m build")
    assert guard_at < build_at

    version = str(runpy.run_path(_ROOT / "src" / "alleleforge" / "_version.py")["__version__"])
    result = _run_guard(f"v{version}")
    assert result.returncode == 0, result.stderr


def test_a_tag_for_another_version_is_refused_before_building() -> None:
    result = _run_guard("v999.0.0")
    assert result.returncode != 0
    assert "does not match package version" in result.stderr


def _run_guard(tag: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "RELEASE_TAG": tag}
    return subprocess.run(
        shlex.split(_version_guard()),
        cwd=_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
