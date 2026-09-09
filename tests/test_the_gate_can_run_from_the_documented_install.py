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


def _gate_extras() -> set[str]:
    """Return the extras `make install` installs."""
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r'^install:.*\n\tpip install -e "\.\[([^\]]+)\]"', makefile, re.M)
    assert match, "the Makefile no longer has an `install` target with a pip line"
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


def test_the_makefile_and_the_ci_jobs_install_the_same_set() -> None:
    """CONTRIBUTING's other half: "the same extras set CI installs, kept in one place"."""
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    gate = _gate_extras()
    running_tests = [
        line
        for line in workflow.splitlines()
        if "pip install -e" in line and "dev" in line and "genome-light" in line
    ]
    assert running_tests, "no CI job installs a dev+genome set; this check would be vacuous"
    for line in running_tests:
        match = re.search(r"\.\[([^\]]+)\]", line)
        assert match, line
        installed = {extra.strip() for extra in match.group(1).split(",")}
        assert gate <= installed, (
            f"`make install` installs {sorted(gate)} and this CI job installs "
            f"{sorted(installed)}, so the gate a contributor runs is not the gate CI runs: "
            f"{line.strip()}"
        )


def test_the_extra_map_is_the_shared_one() -> None:
    """This file reads the CLI's map rather than keeping a second copy of it."""
    assert _EXTRA_FOR_MODULE["polars"] == "core"
    assert _EXTRA_FOR_MODULE["typer"] == "cli"
    assert _EXTRA_FOR_MODULE["fastapi"] == "web"
