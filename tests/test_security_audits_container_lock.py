"""The supply-chain audit examines the versions deployed in the container."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_the_advisory_job_audits_both_python_environments_strictly() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(workflow, dict)
    job: dict[str, Any] = workflow["jobs"]["security"]
    commands = [step["run"] for step in job["steps"] if "run" in step]

    audits = [command for command in commands if command.startswith("pip-audit ")]
    assert audits == [
        "pip-audit --strict --desc -r audit-requirements.txt",
        "pip-audit --strict --desc -r constraints/container.txt",
    ]
    assert job["continue-on-error"] == "true"
