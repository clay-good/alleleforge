"""The release image starts from reviewed, reproducible base bytes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = re.compile(r"^FROM\s+(\S+)\s+AS\s+(\S+)$", re.MULTILINE)
PINNED = re.compile(r"^[^@\s]+:[^@\s]+@sha256:[0-9a-f]{64}$")


def test_every_container_stage_uses_the_same_digest_pinned_base() -> None:
    stages = BASE.findall((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    assert {name for _, name in stages} == {"builder", "runtime"}
    assert all(PINNED.fullmatch(image) for image, _ in stages)
    assert len({image for image, _ in stages}) == 1


def test_dependabot_updates_the_reviewed_base_image_pin() -> None:
    loaded: dict[str, Any] = yaml.safe_load(
        (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    docker = [update for update in loaded["updates"] if update["package-ecosystem"] == "docker"]
    assert docker == [
        {
            "package-ecosystem": "docker",
            "directory": "/",
            "schedule": {"interval": "weekly"},
            "open-pull-requests-limit": 5,
            # Digest refreshes keep flowing; a new Python minor must move with the CI
            # matrix, classifiers and container constraints, so it is never a bot bump.
            "ignore": [
                {
                    "dependency-name": "python",
                    "update-types": ["version-update:semver-major", "version-update:semver-minor"],
                }
            ],
        }
    ]
