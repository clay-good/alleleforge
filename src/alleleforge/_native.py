"""Bridge to the optional Rust extension :mod:`aforge_native`.

The performance-critical kernels (FM-index off-target search, k-mer hashing,
haplotype walking) live in the PyO3 crate under ``rust/`` and are built with
maturin. They are *optional*: AlleleForge imports cleanly without them and
exposes :data:`NATIVE_AVAILABLE` so callers (and tests) can branch on it. This
keeps the pure-Python install path and CI reliable while still proving the
Rust toolchain end to end where it is built.
"""

from __future__ import annotations

from alleleforge._version import __version__

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


def assert_native_matches_python() -> None:
    """Raise if the built crate's version disagrees with the Python package.

    Proves the maturin/PyO3 toolchain is wired to the same single-source
    version. A no-op when the crate is not built.
    """
    nv = native_version()
    if nv is not None and nv != __version__:
        raise RuntimeError(
            f"aforge_native version {nv!r} != alleleforge {__version__!r}; "
            "rebuild the native extension with `maturin develop` in rust/."
        )
