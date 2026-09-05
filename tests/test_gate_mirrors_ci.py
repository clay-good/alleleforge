"""The Makefile's `ci` target must mirror every blocking CI job.

The Makefile's header promises "CI runs the same commands; this is the local mirror
so `make ci` reproduces the gate before a push." That promise was once false: the
`examples` job was missing, and a change that passed lint, types, tests, docs and
reproduce still shipped a broken notebook. A mirror nobody checks drifts toward the
fast, convenient subset — precisely away from the jobs that catch a different class
of failure.

This test is the check. It reads the workflow rather than a hand-maintained list, so
a new CI job fails here until it is either mirrored or explicitly excused below.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]

#: CI jobs deliberately absent from `make ci`, each with the reason it cannot be a
#: blocking local gate. Anything not listed here must be mirrored.
NOT_MIRRORED = {
    "security": "advisory in CI (pip-audit / cargo audit run with `|| true`)",
    "rust": "needs the compiled crate; `make native` covers it on demand",
}

#: CI job id -> the `make` target that runs the same commands.
JOB_TO_TARGET = {
    "lint": "lint",
    "type-check": "type",
    "test": "test",
    "docs": "docs",
    "examples": "examples",
    "reproduce": "reproduce",
}


def _ci_jobs() -> set[str]:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    return set(workflow["jobs"])


def _make_ci_targets() -> list[str]:
    makefile = (ROOT / "Makefile").read_text()
    match = re.search(r"^ci:([^#\n]*)", makefile, re.M)
    assert match is not None, "the Makefile has no `ci:` target"
    return match.group(1).split()


def test_every_blocking_ci_job_is_in_make_ci() -> None:
    targets = _make_ci_targets()
    missing = []
    for job in sorted(_ci_jobs() - set(NOT_MIRRORED)):
        target = JOB_TO_TARGET.get(job)
        if target is None:
            missing.append(f"{job!r} (unknown job: mirror it, or excuse it in NOT_MIRRORED)")
        elif target not in targets:
            missing.append(f"{job!r} -> `make {target}` is not in the `ci` target")
    assert not missing, "make ci no longer mirrors CI: " + "; ".join(missing)


def test_the_excused_jobs_still_exist() -> None:
    """An excuse for a job CI no longer has is stale, and hides the next drift."""
    jobs = _ci_jobs()
    stale = sorted(set(NOT_MIRRORED) - jobs)
    assert not stale, f"NOT_MIRRORED excuses jobs that are gone: {stale}"


def test_every_mirrored_target_exists_in_the_makefile() -> None:
    makefile = (ROOT / "Makefile").read_text()
    for target in JOB_TO_TARGET.values():
        assert re.search(rf"^{target}:", makefile, re.M), f"no `{target}:` target in the Makefile"
