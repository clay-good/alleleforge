"""The runtime image has one copy of AlleleForge: the installed wheel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_the_runtime_copies_the_venv_but_not_the_builder_source_tree() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.count("COPY --from=builder") == 1
    assert "COPY --from=builder /opt/venv /opt/venv" in dockerfile
    assert "COPY --from=builder /app/src" not in dockerfile


def test_ci_proves_the_running_import_comes_from_the_venv() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(workflow, dict)
    steps: list[dict[str, Any]] = workflow["jobs"]["container"]["steps"]
    boot = [step for step in steps if step.get("name") == "Boot image and query health"]
    assert len(boot) == 1
    command = boot[0]["run"]

    assert "pathlib.Path(alleleforge.__file__).is_relative_to('/opt/venv')" in command
    assert "not pathlib.Path('/app/src').exists()" in command
