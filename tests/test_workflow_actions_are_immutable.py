"""Every external workflow action is pinned to immutable code."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USE = re.compile(r"^\s+(?:-\s+)?uses:\s+([^\s#]+)([^\n]*)$", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def test_external_actions_use_full_commit_shas_with_update_hints() -> None:
    offenders: list[str] = []
    found = 0
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for target, suffix in USE.findall(workflow.read_text(encoding="utf-8")):
            if target.startswith("./") or target.startswith("docker://"):
                continue
            found += 1
            action, separator, revision = target.rpartition("@")
            if not action or separator != "@" or not FULL_SHA.fullmatch(revision):
                offenders.append(f"{workflow.name}: {target} is not pinned to a full SHA")
            if not re.fullmatch(r"\s+#\s+\S+\s*", suffix):
                offenders.append(f"{workflow.name}: {target} has no version comment for Dependabot")
    assert found, "no external workflow actions were inspected"
    assert not offenders, "\n".join(offenders)
