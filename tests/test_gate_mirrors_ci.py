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


def test_the_on_demand_rust_gate_runs_what_ci_runs() -> None:
    """`rust` is excused from `make ci`, not from being mirrored.

    Its excuse says "`make native` covers it on demand" — a claim about commands that
    nothing compared, on the one job this file lets out of the main check. That is the
    same shape as the `lint` divergence in the docstring above: an excuse phrased as a
    promise, with no check behind it.

    Compared on the test invocation rather than the whole recipe, because the build
    steps legitimately differ: CI installs the wheel it just built into a fresh runner,
    and `make native` has to `--force-reinstall` over the developer's existing one.
    """
    assert NOT_MIRRORED.get("rust"), "this test is about the excused rust job"
    ci_tests = [c for c in _job_commands("rust") if c.startswith("pytest")]
    make_tests = [c for c in _target_commands("native") if c.startswith("pytest")]
    assert ci_tests, "CI's rust job runs no pytest command"
    assert ci_tests == make_tests, (
        f"CI's rust job runs {ci_tests} and `make native` runs {make_tests}. The excuse "
        "for leaving `rust` out of `make ci` is that `make native` covers it, which is "
        "only true while they run the same tests."
    )


def test_the_rust_job_runs_the_whole_suite_not_only_the_native_marks() -> None:
    """Every other job runs the pure-Python configuration.

    With the crate installed the library takes its native branches everywhere, and that
    is the configuration the docs recommend for real work — so a `-m native` selection
    here means the shipped configuration is exercised only where someone remembered to
    add a marker. It has bitten before: with the crate built, `FMIndex.build` dispatched
    to the extension and silently dropped `cache_dir`, `rebuild`, `occ_rate` and
    `sa_rate`, which no `native`-marked test covered.
    """
    ci_tests = [c for c in _job_commands("rust") if c.startswith("pytest")]
    assert ci_tests and all("-m native" not in c for c in ci_tests), ci_tests


def test_the_readme_points_at_the_mirror_rather_than_respelling_it() -> None:
    """The third surface, which this file did not read.

    `make ci` mirrors CI and is compared to it by command. The README carried its own
    hand-spelled copy of the same gate — a third place for it to drift, checked by
    nothing — and it had: `ruff` over three paths where CI ran four, which is the exact
    divergence this file's docstring was written about, and `maturin develop`, which
    installs a build of the working tree into whatever virtualenv is active rather than
    the wheel CI installs.

    The fix is not to compare a third copy but to remove it: the README points at the
    targets, and this keeps it pointing rather than respelling. A `ruff`/`mypy`/`pytest`
    invocation in the development section means someone has started a fourth copy.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("## Development")
    section = readme[start : start + 2000]
    # Command lines only. The prose around them legitimately names the tools — including
    # the sentence explaining why they are no longer spelled out here — and a needle that
    # cannot tell an instruction from a mention libels the explanation.
    commands = [
        line.strip()
        for block in re.findall(r"```bash\n(.*?)```", section, re.S)
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert commands, "the development section has no command block"

    assert "make ci" in section, "the development section no longer points at `make ci`"
    respelled = [
        tool
        for tool in ("ruff check", "ruff format", "mypy --strict", "pytest ", "maturin develop")
        if any(tool in command for command in commands)
    ]
    assert not respelled, (
        f"the README's development section spells out {respelled} instead of pointing at "
        "the make targets. That is a second copy of the gate, and the one nothing "
        "compares to CI — it drifted to three `ruff` paths against CI's four last time."
    )


def test_no_document_tells_a_contributor_to_maturin_develop() -> None:
    """`maturin develop` installs the working tree into the active virtualenv.

    Which is shared by every checkout using it, and goes stale the moment the tree moves.
    CI installs the built wheel, `make native` does the same, and a contributor following
    the docs should end up where CI is — especially in a repository where several
    worktrees of the same project are normal.
    """
    offenders = []
    for path in [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]:
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            # The prose that *warns* about it names it too; only a command line counts.
            stripped = line.strip()
            if stripped.startswith(
                ("maturin develop", "cd rust && maturin develop", "$ maturin develop")
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, (
        f"these tell a contributor to run `maturin develop`: {offenders}. Point at "
        "`make native`, which builds a wheel and installs that, as CI does."
    )
