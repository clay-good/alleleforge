"""Every downloadable release artifact is covered by one digest manifest."""

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


def _downloads(job: dict[str, Any]) -> dict[str, str]:
    return {
        step["with"]["name"]: step["with"]["path"]
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/download-artifact@")
    }


def test_checksums_cover_the_validated_distributions_and_wheel_sbom() -> None:
    job = _workflow()["jobs"]["checksums"]

    assert set(job["needs"]) == {"build", "sbom"}
    assert _downloads(job) == {"dist": "artifacts", "sbom": "artifacts"}
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "cd artifacts && sha256sum * > ../SHA256SUMS" in commands

    uploads = [
        step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    assert len(uploads) == 1
    assert uploads[0]["with"] == {"name": "checksums", "path": "SHA256SUMS"}


def test_the_checksum_manifest_is_attached_beside_the_files_it_names() -> None:
    release = _workflow()["jobs"]["github-release"]

    assert _downloads(release) == {
        "dist": "dist",
        "sbom": "dist",
        "checksums": "dist",
    }
