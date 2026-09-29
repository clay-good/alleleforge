"""The default deployment gives the web process only the writes it needs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_compose_confines_the_service_and_names_its_two_writable_mounts() -> None:
    app = _yaml(ROOT / "docker-compose.yml")["services"]["app"]

    assert app["read_only"] is True
    assert app["cap_drop"] == ["ALL"]
    assert app["security_opt"] == ["no-new-privileges:true"]
    assert app["tmpfs"] == ["/tmp:mode=1777,uid=10001,gid=10001"]
    assert "aforge-cache:/cache" in " ".join(app["volumes"])


def test_ci_boots_the_real_service_under_the_same_restrictions() -> None:
    workflow = _yaml(ROOT / ".github" / "workflows" / "ci.yml")
    steps = workflow["jobs"]["container"]["steps"]
    boot = [step for step in steps if step.get("name") == "Boot image and query health"]
    assert len(boot) == 1
    command = boot[0]["run"]

    for restriction in (
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges:true",
        "--tmpfs /tmp:mode=1777,uid=10001,gid=10001",
        "--tmpfs /cache:mode=0755,uid=10001,gid=10001",
    ):
        assert restriction in command
    assert "pathlib.Path('/cache/ci-smoke').write_text('ok')" in command


def test_the_deployment_guide_explains_the_writable_paths() -> None:
    guide = " ".join((ROOT / "docs" / "deployment.md").read_text(encoding="utf-8").split())

    assert "read-only root filesystem" in guide
    assert "drops every Linux capability" in guide
    assert "`no-new-privileges`" in guide
    assert "`/tmp`" in guide and "`/cache`" in guide
