"""Local biological data never enters the Docker build context."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_build_context_is_an_explicit_allowlist() -> None:
    lines = [
        line
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]

    assert lines == [
        "*",
        "!pyproject.toml",
        "!README.md",
        "!constraints/",
        "!constraints/container.txt",
        "!src/",
        "!src/**",
    ]


def test_the_dockerfile_never_reintroduces_the_whole_context() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copies = re.findall(r"^COPY\s+(?!--from=)(.+)$", dockerfile, re.MULTILINE)

    assert copies == [
        "pyproject.toml README.md constraints/container.txt ./",
        "src ./src",
    ]
    assert all(source not in {".", "./"} for copy in copies for source in copy.split()[:-1])


def test_the_deployment_guide_names_the_private_data_boundary() -> None:
    guide = " ".join((ROOT / "docs" / "deployment.md").read_text(encoding="utf-8").split())

    assert "deny-by-default build context" in guide
    assert "`./data` never enters the image build" in guide
