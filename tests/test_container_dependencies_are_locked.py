"""The deployment image resolves one reviewed Python dependency graph."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "constraints" / "container.txt"
PIN = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s]+)$")


def _pins() -> list[tuple[str, str]]:
    pins = []
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        assert match is not None, f"container dependency is not exact: {line}"
        pins.append((match["name"], match["version"]))
    return pins


def test_the_container_lock_is_exact_complete_enough_and_stably_ordered() -> None:
    pins = _pins()

    assert len(pins) >= 30
    assert len({name.lower().replace("_", "-") for name, _version in pins}) == len(pins)
    assert pins == sorted(pins, key=lambda pin: f"{pin[0]}=={pin[1]}")


def test_the_docker_build_constrains_the_deployment_install() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY pyproject.toml README.md constraints/container.txt ./" in dockerfile
    assert 'pip install --constraint container.txt ".[core,cli,web,genome-light]"' in dockerfile


def test_local_and_ci_smokes_compare_the_image_with_the_lock() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["container"]["steps"])

    expected = "freeze --exclude alleleforge"
    assert expected in makefile
    assert expected in commands
    assert "diff -u constraints/container.txt" in makefile
    assert "diff -u constraints/container.txt" in commands
