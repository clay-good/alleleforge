"""The Makefile's `ci` target must mirror every blocking CI job.

The Makefile's header promises "CI runs the same commands; this is the local mirror
so `make ci` reproduces the gate before a push." That promise was once false: the
`examples` job was missing, and a change that passed lint, types, tests, docs and
reproduce still shipped a broken notebook. A mirror nobody checks drifts toward the
fast, convenient subset — precisely away from the jobs that catch a different class
of failure.

This test is the check. It reads the workflow rather than a hand-maintained list, so
a new CI job fails here until it is either mirrored or explicitly excused below.

Checking that the job *names* line up was not enough. A commit called "extend the ruff
gate to the example notebooks so they can't drift" added `examples` to CI's
`ruff check`/`ruff format --check` and left the Makefile's `lint` target on
`src tests scripts` — so `make ci` reported a green lint over three paths while CI ran
four, and a notebook that fails `ruff format --check` sat on `main` where the local
gate could not see it. A mirror that matches names and not commands is a mirror of the
list of jobs, not of the gate. So the commands are compared too.
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


def _job_commands(job: str) -> list[str]:
    """Return the `run:` steps of a CI job, minus environment setup."""
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = workflow["jobs"][job].get("steps", [])
    return [
        " ".join(step["run"].split())
        for step in steps
        if isinstance(step, dict) and "run" in step and "pip install" not in step["run"]
    ]


def _target_commands(target: str) -> list[str]:
    """Return the recipe lines of a Makefile target."""
    makefile = (ROOT / "Makefile").read_text()
    match = re.search(rf"^{target}:.*?\n((?:\t.*\n)+)", makefile, re.M)
    assert match is not None, f"no `{target}:` recipe in the Makefile"
    return [" ".join(line.split()) for line in match.group(1).splitlines() if line.strip()]


#: `(job, target)` pairs whose commands differ for a stated reason. Empty is the goal.
COMMANDS_DIFFER: dict[str, str] = {}


@pytest.mark.parametrize("job, target", sorted(JOB_TO_TARGET.items()))
def test_a_mirrored_job_runs_the_same_commands(job: str, target: str) -> None:
    """The gate is the commands, not the job names.

    `make ci` promises to reproduce the gate before a push. It can only do that if the
    mirrored target runs what the job runs — the `lint` divergence above passed this
    file's other checks for as long as it existed.
    """
    reason = COMMANDS_DIFFER.get(job)
    ci, make = _job_commands(job), _target_commands(target)
    if reason:
        assert ci != make, f"{job} now matches `make {target}`; drop its COMMANDS_DIFFER entry"
        return
    assert ci == make, (
        f"CI job {job!r} runs {ci} but `make {target}` runs {make}. `make ci` would "
        "report green over a gate CI runs differently — mirror it, or record the "
        "difference in COMMANDS_DIFFER with the reason."
    )


def test_the_command_comparison_is_not_vacuous() -> None:
    """Guard the guard: both readers must actually find commands."""
    assert _job_commands("lint"), "no CI commands parsed"
    assert _target_commands("lint"), "no Makefile recipe parsed"
    assert "examples" in " ".join(_job_commands("lint"))
