"""Release publication is gated and each job holds only the authority it uses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> dict[str, Any]:
    loaded = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def _needs(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else set(needs)


def test_write_authority_is_scoped_to_the_jobs_that_publish() -> None:
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    overrides = {name: job["permissions"] for name, job in jobs.items() if "permissions" in job}
    assert overrides == {
        "pypi": {"id-token": "write"},
        "docker": {"contents": "read", "packages": "write"},
        "github-release": {"contents": "write"},
    }


def test_nothing_is_published_before_the_required_sbom_passes() -> None:
    jobs = _workflow()["jobs"]
    assert {"build", "sbom", "checksums"} <= _needs(jobs["pypi"])
    assert {"build", "sbom", "checksums"} <= _needs(jobs["docker"])
    assert {"sbom", "pypi", "docker"} <= _needs(jobs["github-release"])
