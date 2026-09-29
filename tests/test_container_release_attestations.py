"""The published image carries evidence about its contents and build."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> dict[str, Any]:
    loaded = yaml.load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(loaded, dict)
    return loaded


def test_the_published_multiarch_image_has_explicit_max_provenance_and_an_sbom() -> None:
    steps = _workflow()["jobs"]["docker"]["steps"]
    publishers = [
        step
        for step in steps
        if step.get("uses", "").startswith("docker/build-push-action@")
        and step.get("with", {}).get("push") == "true"
    ]

    assert len(publishers) == 1
    inputs = publishers[0]["with"]
    assert inputs["platforms"] == "linux/amd64,linux/arm64"
    assert inputs["provenance"] == "mode=max"
    assert inputs["sbom"] == "true"


def test_release_docs_distinguish_the_image_sbom_from_the_wheel_sbom() -> None:
    release = " ".join((ROOT / "RELEASE.md").read_text(encoding="utf-8").split())

    assert "OCI-attached SBOM" in release
    assert "wheel's CycloneDX SBOM" in release
    assert "max-level build provenance" in release
