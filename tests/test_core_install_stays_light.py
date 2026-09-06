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


def test_the_probe_would_notice_a_heavy_import() -> None:
    """Guard the guard: the probe must actually observe sys.modules."""
    probe = _PROBE.replace("import sys, alleleforge", "import sys, alleleforge, typer")
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert "typer" in proc.stdout
