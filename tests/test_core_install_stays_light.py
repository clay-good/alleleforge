"""`import alleleforge` must not drag in the optional stacks.

The deployment guide promises the core install is "deliberately minimal (pydantic
types, config, model-card parsing) so it imports fast and stays reliable", with the
heavy scientific, ML, genome and web stacks in optional groups "pulled in only where
needed". That is a real promise — a `pip install alleleforge` has eight transitive
dependencies and none of them is numpy — and nothing checked it.

It is also one line from being false. A top-level `import numpy` added to any module
the package's `__init__` chain touches would make the core install fail outright on a
machine that has no numpy, and no test in this suite would notice, because CI installs
every extra. This runs the import in a subprocess with a clean interpreter and asks
what it loaded.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

#: Third-party roots that belong to an optional extra, never to the core install.
_OPTIONAL_ROOTS = (
    "numpy",
    "pandas",
    "polars",
    "pyarrow",
    "torch",
    "transformers",
    "lightning",
    "sklearn",
    "lightgbm",
    "pyfaidx",
    "pysam",
    "cyvcf2",
    "mappy",
    "pyliftover",
    "hgvs",
    "fastapi",
    "uvicorn",
    "typer",
    "click",
)

#: Subpackages a documented extra must reach without *any* optional stack.
#: `pip install alleleforge[cli]` does not install pyfaidx, so a command that needs no
#: reference genome must not require it to import.
_LIGHT_SUBPACKAGES = (
    "alleleforge.data",
    "alleleforge.model_zoo",
    # These joined the list when the deferral was finished. `alleleforge.benchmark` was
    # excluded here with a note calling the rest "a refactor rather than a correction":
    # its chain reached `viz.figures`, which builds a fixture FASTA. The chain is gone —
    # ten modules imported `genome.reference` directly for an *annotation*, walking past
    # the deferral `genome/__init__` already had, and `viz.figures` now imports it inside
    # the one function that constructs one.
    "alleleforge.benchmark",
    "alleleforge.design",
    "alleleforge.enumerate",
    "alleleforge.genome",
    "alleleforge.offtarget",
    "alleleforge.report",
    "alleleforge.scoring",
    "alleleforge.variant",
    "alleleforge.viz",
)

#: The stack a `[cli]` install does not have. `alleleforge.cli.main` legitimately loads
#: typer — that is what `[cli]` installs — so it is checked against these alone.
_GENOME_ROOTS = ("pyfaidx", "pysam", "cyvcf2", "mappy", "pyliftover", "hgvs")

_PROBE = (
    "import sys, alleleforge\n"
    'roots = {m.split(".")[0] for m in sys.modules}\n'
    f"print(','.join(sorted(roots & set({_OPTIONAL_ROOTS!r}))))\n"
)


def test_importing_the_package_loads_no_optional_stack() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, check=True
    )
    loaded = [m for m in proc.stdout.strip().split(",") if m]
    assert not loaded, (
        f"`import alleleforge` pulled in optional dependencies: {loaded}. The core "
        "install does not have them, so this makes it fail on a clean machine. Move "
        "the import inside the function that needs it."
    )


@pytest.mark.parametrize("module", _LIGHT_SUBPACKAGES)
def test_a_light_subpackage_loads_no_optional_stack(module: str) -> None:
    """The promise is per entry point, and only the top-level one was checked.

    `import alleleforge` was clean while `import alleleforge.benchmark` pulled in
    pyfaidx, so `aforge bench run` on a `[cli]` install died with a traceback. CI
    installs every extra, which is why nothing noticed.
    """
    probe = _PROBE.replace("import sys, alleleforge\n", f"import sys, {module}\n")
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    loaded = [m for m in proc.stdout.strip().split(",") if m]
    assert not loaded, (
        f"`import {module}` pulled in optional dependencies: {loaded}. A command that "
        "needs no reference genome must not require the genome stack to import."
    )


def test_the_probe_would_notice_a_heavy_import() -> None:
    """Guard the guard: the probe must actually observe sys.modules."""
    probe = _PROBE.replace("import sys, alleleforge", "import sys, alleleforge, typer")
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert "typer" in proc.stdout


def test_the_cli_entry_point_imports_without_the_genome_stack() -> None:
    """`pip install "alleleforge[cli]"` must produce an `aforge` that runs.

    It did not. Every command — `--version`, `--help`, `data list`, `bench list` —
    died with `ModuleNotFoundError: No module named 'pyfaidx'` before the argument
    parser saw the line, because `cli.main` imports `design`, which reached
    `genome.reference` and its module-level `from pyfaidx import Fasta`. The install
    table in the deployment guide lists genome access as a separate row to *add*,
    which is exactly the promise this breaks.

    Checked against the genome stack only: typer is what `[cli]` installs.
    """
    probe = (
        "import sys, alleleforge.cli.main\n"
        'roots = {m.split(".")[0] for m in sys.modules}\n'
        f"print(','.join(sorted(roots & set({_GENOME_ROOTS!r}))))\n"
    )
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    loaded = [m for m in proc.stdout.strip().split(",") if m]
    assert not loaded, (
        f"importing the CLI pulled in the genome stack: {loaded}. Every `aforge` command "
        "then requires it, including the ones that read no sequence."
    )


def test_opening_a_reference_without_pyfaidx_says_which_install_gives_it() -> None:
    """The one thing that does need it must refuse in words, not from three frames down."""
    from alleleforge.errors import MissingDependencyError
    from alleleforge.genome import reference as reference_module

    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "pyfaidx", None)
        with pytest.raises(MissingDependencyError) as excinfo:
            reference_module._fasta_reader()
    message = str(excinfo.value)
    assert "pyfaidx" in message, message
    assert "alleleforge[genome" in message, message
