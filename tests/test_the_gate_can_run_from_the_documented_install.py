"""`pytest` could not collect the suite from the documented install.

`tests/report/test_the_parquet_schema_is_declared_not_guessed.py` opens with a bare
``import polars as pl``. `polars` is the `core` extra, and `core` was in neither
`make install` (`[dev,cli,web,genome-light]`) nor any CI job that runs tests. In a clean
venv built from that exact set:

    ERROR tests/report/test_the_parquet_schema_is_declared_not_guessed.py
    ModuleNotFoundError: No module named 'polars'
    !!!!! Interrupted: 1 error during collection !!!!!

Not one test ran. It stayed invisible because the development virtualenv on this machine
has `polars` installed ad hoc — and *not* `pyarrow` or `numpy`, the other two members of
the same extra, which is the signature of a package added by hand to make something pass
rather than by the documented command.

The same hole sits one gate member over. `make ci` is `lint type test docs examples
reproduce`, and `make docs` runs `mkdocs build --strict` — while `make install` did not
install the `docs` extra. A contributor following CONTRIBUTING to the letter got
``make: mkdocs: No such file or directory``. Found by diffing this machine's virtualenv
against a clean documented install: mkdocs was in the former and not the latter, along
with `polars`.

`CONTRIBUTING.md` states the property this file checks, and states it as the reason
`make install` exists: *"`dev` alone leaves out the FASTA reader and the web server, so
the gate you are about to run cannot pass. It is the same extras set CI installs, kept in
one place."* Both halves had drifted — the set did not carry the gate, and it was no longer
the same one CI installed after this fix, so both moved together.

The check derives the required extras rather than listing them: `cli.main._EXTRA_FOR_MODULE`
already maps every optional import to the extra that provides it, because the CLI needs it
to turn an ImportError into an install line. A test importing one of those modules at
module scope needs its extra in the gate.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from alleleforge.cli.main import _EXTRA_FOR_MODULE

_ROOT = Path(__file__).resolve().parents[1]
_TESTS = _ROOT / "tests"


def _makefile_target(name: str, makefile: str) -> str:
    """Return the body of one Makefile target, comments and all.

    Reads to the next target rather than to the next unindented line: a `#` comment at
    column 0 is part of a recipe's explanation, and a reader that stopped at one broke
    the moment a target was documented — the wrong thing for a guard to be fragile about.
    """
    lines: list[str] = []
    for line in makefile.splitlines():
        if lines and re.match(r"^[a-z][\w-]*:", line):
            break
        if lines or line.startswith(f"{name}:"):
            lines.append(line)
    assert lines, f"the Makefile no longer has a `{name}` target"
    return "\n".join(lines)


def _gate_extras() -> set[str]:
    """Return the extras `make install` installs."""
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    # Comment lines may sit between the target and its recipe, so match the pip line
    # anywhere in the block rather than immediately after the colon — a rule that broke
    # the first time a comment was added, which is the wrong thing to be fragile about.
    block = _makefile_target("install", makefile)
    match = re.search(r'pip install -e "\.\[([^\]]+)\]"', block)
    assert match, f"the `install` target no longer runs a pip install:\n{block}"
    return {extra.strip() for extra in match.group(1).split(",")}


def _module_scope_imports() -> dict[str, list[str]]:
    """Return ``{module: [test files that import it at module scope]}``.

    Module scope only. An import inside a function or a fixture fails that test; an
    import at module scope fails *collection*, which stops the whole run — which is why
    this one was a broken gate rather than one red test.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(_TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:  # top level only
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                found.setdefault(name, []).append(path.relative_to(_ROOT).as_posix())
    return found


def _ci_jobs_that_run_the_suite() -> dict[str, set[str]]:
    """Return ``{job: extras installed}`` for CI jobs whose steps run the test suite.

    Only those. The `reproduce` job installs `[dev,core,genome-light]` and runs
    `scripts/reproduce.py`, which needs neither the CLI nor the web stack — holding it to
    the full gate set would demand dependencies for something it never imports, and a
    check that asks for what is not needed gets loosened rather than obeyed.
    """
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    jobs: dict[str, set[str]] = {}
    current: str | None = None
    installed: set[str] = set()
    runs_suite = False
    for line in [*workflow.splitlines(), "  __end__:"]:
        job = re.match(r"^  ([\w-]+):\s*$", line)
        if job:
            if current and runs_suite:
                jobs[current] = installed
            current, installed, runs_suite = job.group(1), set(), False
            continue
        if current is None:
            continue
        install = re.search(r'pip install -e "\.\[([^\]]+)\]"', line)
        if install:
            installed = {extra.strip() for extra in install.group(1).split(",")}
        # `pytest` with no path runs the whole suite; `pytest --nbmake examples/` does not.
        if re.search(r"run:\s*pytest\s*(--no-cov)?\s*$", line):
            runs_suite = True
    return jobs


def test_the_reader_finds_imports() -> None:
    """A parse that produced nothing would make every check below vacuous."""
    imports = _module_scope_imports()
    assert "pytest" in imports, sorted(imports)[:20]


def test_every_optional_module_a_test_imports_is_in_the_gate() -> None:
    """The property CONTRIBUTING already promises: the gate's set can run the gate."""
    gate = _gate_extras()
    imports = _module_scope_imports()
    missing = sorted(
        f"{module} (extra `{extra}`) imported at module scope by {files[0]}"
        for module, extra in _EXTRA_FOR_MODULE.items()
        if (files := imports.get(module)) and extra not in gate
    )
    assert not missing, (
        "these tests fail *collection* — stopping the whole run — on an environment built "
        f"by `make install`, whose extras are {sorted(gate)}: {missing}. Add the extra to "
        "the Makefile target and to the CI jobs that run tests, or import the module "
        "inside the test that needs it."
    )


def _extras_collection_needs() -> set[str]:
    """Return the extras without which `pytest` cannot *collect* the suite."""
    imports = _module_scope_imports()
    return {extra for module, extra in _EXTRA_FOR_MODULE.items() if module in imports}


def test_every_ci_job_that_runs_the_suite_can_collect_it() -> None:
    """Not "the same set as `make install`" — CI splits the gate across jobs, and the job
    that runs `pytest` has no use for mkdocs. What every one of them needs is whatever an
    import at module scope requires, because without it nothing in that job runs at all.

    Both jobs that run the suite failed this: `test` lacked `core`, and `rust` — which
    runs the whole suite by a deliberate decision, with eleven lines of comment explaining
    why — lacked `core`, `cli` and `web`.
    """
    required = _extras_collection_needs()
    assert required, "no collection-time extras found; this check would be vacuous"
    jobs = _ci_jobs_that_run_the_suite()
    assert jobs, "no CI job runs the suite; this check would be vacuous"
    for name, installed in sorted(jobs.items()):
        missing = sorted(required - installed)
        assert not missing, (
            f"the CI job `{name}` runs the suite and installs {sorted(installed)}, which "
            f"is missing {missing}. A test imports one of those at module scope, so "
            "pytest fails at collection and no test in that job runs."
        )


def test_the_gate_install_covers_what_collection_needs() -> None:
    """And `make install`, the one environment that must run every gate member."""
    missing = sorted(_extras_collection_needs() - _gate_extras())
    assert not missing, missing


def test_the_extra_map_is_the_shared_one() -> None:
    """This file reads the CLI's map rather than keeping a second copy of it."""
    assert _EXTRA_FOR_MODULE["polars"] == "core"
    assert _EXTRA_FOR_MODULE["typer"] == "cli"
    assert _EXTRA_FOR_MODULE["fastapi"] == "web"


# --- the same question for the tools, not the imports ---------------------------


#: Executables `make ci` invokes that pip cannot supply, with what does.
_NOT_FROM_PIP: dict[str, str] = {
    "node": "`make lint` parses the served page's script with `node --check`. It is a "
    "system runtime, not a Python package — CI installs it with actions/setup-node, and "
    "a contributor without it sees the command's own 'not found' rather than a wrong "
    "answer",
    "python": "the interpreter running the Makefile",
}

#: The extra that provides each remaining gate executable. Small and explicit: a console
#: script's name is not derivable from a distribution name (`mkdocs` comes from
#: `mkdocs-material`), and guessing is how a check like this quietly stops meaning
#: anything.
_TOOL_EXTRA: dict[str, str] = {
    "ruff": "dev",
    "mypy": "dev",
    "pytest": "dev",
    "mkdocs": "docs",
}


def _gate_executables() -> set[str]:
    """Return the executables every target `make ci` depends on actually runs."""
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    bodies = dict(re.findall(r"(?m)^([a-z][\w-]*):[^\n]*\n((?:(?:#[^\n]*|\t[^\n]*)\n)*)", makefile))
    members = re.search(r"(?m)^ci:\s*([^#\n]+)", makefile)
    assert members, "the Makefile no longer has a `ci` target"
    found: set[str] = set()
    for target in members.group(1).split():
        for line in bodies.get(target, "").splitlines():
            if not line.startswith("\t"):
                continue
            words = line.strip().split()
            if words:
                found.add(words[0])
    assert len(found) >= 4, f"parsed {found} — this check would be vacuous"
    return found


def test_every_tool_the_gate_runs_is_installed_or_recorded() -> None:
    """`make install` must be able to run `make ci`, which is why it exists."""
    gate = _gate_extras()
    unavailable = sorted(
        f"{tool} (extra `{_TOOL_EXTRA[tool]}`)"
        for tool in _gate_executables()
        if tool in _TOOL_EXTRA and _TOOL_EXTRA[tool] not in gate
    )
    assert not unavailable, (
        f"`make ci` runs these and `make install` ({sorted(gate)}) does not provide "
        f"them: {unavailable}. A contributor gets 'command not found' on a gate the "
        "project told them to run."
    )


def test_every_gate_tool_is_accounted_for() -> None:
    """A tool in neither map is one nobody decided about."""
    unaccounted = sorted(_gate_executables() - set(_TOOL_EXTRA) - set(_NOT_FROM_PIP))
    assert not unaccounted, (
        f"`make ci` runs {unaccounted} and nothing records where they come from. Add the "
        "extra to _TOOL_EXTRA, or the reason to _NOT_FROM_PIP."
    )


def test_no_recorded_tool_outlives_the_gate() -> None:
    """An entry for a tool the gate no longer runs hides the next one."""
    running = _gate_executables()
    stale = sorted((set(_TOOL_EXTRA) | set(_NOT_FROM_PIP)) - running)
    assert not stale, f"recorded as gate tools, but `make ci` no longer runs them: {stale}"
