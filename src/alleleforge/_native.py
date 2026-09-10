"""Bridge to the optional Rust extension :mod:`aforge_native`.

The performance-critical kernels (FM-index off-target search, k-mer hashing,
haplotype walking, bulged alignment) live in the PyO3 crate under ``rust/`` and are built with
maturin. They are *optional*: AlleleForge imports cleanly without them and
exposes :data:`NATIVE_AVAILABLE` so callers (and tests) can branch on it. This
keeps the pure-Python install path and CI reliable while still proving the
Rust toolchain end to end where it is built.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge._version import __version__
from alleleforge.errors import MissingDependencyError

try:
    import aforge_native as _ext

    NATIVE_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the built crate
    _ext = None
    NATIVE_AVAILABLE = False


def native_version() -> str | None:
    """Return the compiled crate's version, or ``None`` if it is not built."""
    if _ext is None:
        return None
    version: str = _ext.version()
    return version


def acceleration() -> str:
    """Return one line saying whether this install runs the native kernels.

    The kernels are proven by a parity suite to return exactly what the Python
    implementation returns, so switching between them changes no result — which is the
    right property and makes the difference invisible: an install without the extension,
    or with a stale one, produces identical output an order of magnitude slower, and
    nothing anywhere said which was happening.

    Worded here rather than in a shell, so the command line, the web API's health report
    and a Python caller cannot describe the same install three ways.
    """
    version = native_version()
    if version is None:
        return (
            "native kernels: not installed (pure Python; results are identical and the "
            "off-target hot path is markedly slower — build the crate with maturin)"
        )
    missing = missing_native_functions()
    if missing:
        return (
            f"native kernels: aforge_native {version}, STALE — the installed extension "
            f"is missing {', '.join(sorted(missing))}, so those kernels fall back to "
            "Python and their parity tests skip themselves. Rebuild it with maturin"
        )
    return f"native kernels: aforge_native {version}"


def crate_pyfunctions() -> frozenset[str]:
    """Return the function names ``rust/src/lib.rs`` registers on the module.

    Read from the source rather than from the built module, because the point is to
    compare the two: this is what a *current* build would export.
    """
    lib = Path(__file__).resolve().parents[2] / "rust" / "src" / "lib.rs"
    if not lib.is_file():  # pragma: no cover - a wheel install ships no crate source
        return frozenset()
    return frozenset(re.findall(r"wrap_pyfunction!\(\s*(\w+)\s*,", lib.read_text(encoding="utf-8")))


def missing_native_functions() -> frozenset[str]:
    """Return kernels the crate registers that the *installed* extension lacks.

    Non-empty means the built extension is stale — older than the crate source it sits
    beside. That state is invisible to the version handshake below, because the crate
    version is single-sourced from the package version and does not change between
    builds during development: an extension built before a kernel was added reports the
    same version as one built after it.

    It is not a harmless staleness. The kernel this catches is the off-target
    evaluation hot path, whose *entire* safety argument is a parity suite proving it
    returns what the Python implementation returns — and those tests skip themselves
    when the kernel is absent, reporting "not built". So a stale extension silently
    withdraws the tests that exist to catch native/Python divergence, and says something
    untrue about why.
    """
    if _ext is None:
        return frozenset()
    return frozenset(name for name in crate_pyfunctions() if not hasattr(_ext, name))


def assert_native_matches_python() -> None:
    """Raise if the built crate disagrees with the Python package it sits beside.

    Two ways it can. The version handshake proves the maturin/PyO3 toolchain is wired to
    the same single-source version. The export check proves the *build* is current,
    which the version cannot: see :func:`missing_native_functions`.

    `MissingDependencyError` rather than a bare `RuntimeError`, for both: the remedy is
    an install action the reader takes — rebuild the extension — not a defect to report,
    which is the distinction that type exists to keep. The suite's own check for this
    caught the staleness error in the round that added it.

    A no-op when the crate is not built.

    Raises:
        MissingDependencyError: If the built crate's version disagrees, or the installed
            extension is older than the crate source beside it.
    """
    nv = native_version()
    if nv is not None and nv != __version__:
        raise MissingDependencyError(
            f"aforge_native version {nv!r} != alleleforge {__version__!r}; "
            "rebuild the native extension with `maturin develop` in rust/."
        )
    missing = missing_native_functions()
    if missing:
        raise MissingDependencyError(
            f"the installed aforge_native is stale: the crate registers "
            f"{', '.join(sorted(missing))} and the built extension does not export "
            f"{'it' if len(missing) == 1 else 'them'}. Its version matches, because the "
            "crate version is single-sourced and does not change between builds. "
            "Rebuild with `maturin develop` in rust/ — until then the parity tests for "
            "those kernels skip themselves, reporting that the crate is not built."
        )
