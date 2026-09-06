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

#: Subpackages a documented extra must reach without the *genome* stack.
#: `pip install alleleforge[cli]` does not install pyfaidx, so a command that needs no
#: reference genome must not require it to import.
_LIGHT_SUBPACKAGES = ("alleleforge.data", "alleleforge.model_zoo")

#: `alleleforge.benchmark` is *not* here yet, deliberately. Its chain reaches
#: `viz.figures`, which builds a fixture FASTA and needs `ReferenceGenome` at runtime,
#: so making the whole benchmark stack genome-free is a refactor rather than a
#: correction. Two links were removed (the `enumerate` modules annotate with
#: `ReferenceGenome` and now import it under `TYPE_CHECKING`; `genome/__init__` defers
#: its `reference` re-exports), and the user-visible defect — `aforge bench` dying with
#: a raw `ModuleNotFoundError` where every sibling command explains itself — is fixed
#: and pinned in `tests/cli/test_bench_reports_a_missing_dependency.py`.

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
