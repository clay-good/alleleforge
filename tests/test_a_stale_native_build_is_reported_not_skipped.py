"""A stale extension withdrew the tests that exist to catch native/Python divergence.

`aforge_native` was installed in this machine's environment and did not export
`evaluate_anchor` — the off-target evaluation kernel — because it had been built before
that kernel was added. Seventeen parity tests skipped themselves, reporting "native
aforge_native evaluate kernel not built", which was not true: it was built, and old.

The handshake that exists for this could not see it. `assert_native_matches_python`
compares the crate's version to the package's, and the crate version is single-sourced
from the package version — so it does not change between builds during development, and
an extension built before a kernel was added reports exactly the version of one built
after it.

That matters more than a stale build usually would. The native kernel's entire safety
argument is a parity suite proving it returns what the Python implementation returns, and
that suite disables itself precisely when the kernel is missing. So the failure mode is:
the extension silently falls behind, the tests that would notice remove themselves, and
the message blames a build nobody skipped.

The check compares what `rust/src/lib.rs` registers against what the installed module
exports — the one comparison that distinguishes "not built" from "built, and older than
the source next to it".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge import _native
from alleleforge.errors import MissingDependencyError

_LIB = Path(__file__).resolve().parents[1] / "rust" / "src" / "lib.rs"


def test_the_registered_kernels_are_read_from_the_crate() -> None:
    """A floor: an empty set would make every check below vacuously true."""
    registered = _native.crate_pyfunctions()
    assert len(registered) >= 5, f"parsed {registered} from lib.rs"
    assert "evaluate_anchor" in registered, (
        "the kernel whose absence started this is no longer registered; if it was "
        "renamed, this test and the parity suite's skip condition both need updating"
    )
    # Parsed, not hardcoded: the source is the thing that changes.
    assert registered == frozenset(
        re.findall(r"wrap_pyfunction!\(\s*(\w+)\s*,", _LIB.read_text(encoding="utf-8"))
    )


def test_a_build_missing_a_registered_kernel_is_reported() -> None:
    """The state that was silent: installed, importable, and behind the source."""

    class _Stale:
        """An extension that exports everything except the newest kernel."""

        def version(self) -> str:
            return _native.__version__

        def __getattr__(self, name: str) -> object:
            if name == "evaluate_anchor":
                raise AttributeError(name)
            return lambda *a, **k: None

    original = _native._ext
    try:
        _native._ext = _Stale()  # type: ignore[assignment]
        assert _native.missing_native_functions() == frozenset({"evaluate_anchor"})
        with pytest.raises(MissingDependencyError) as raised:
            _native.assert_native_matches_python()
    finally:
        _native._ext = original
    message = str(raised.value)
    assert "stale" in message, message
    assert "evaluate_anchor" in message, "the message must name what is missing"
    assert "maturin develop" in message, "and the command that fixes it"


def test_an_absent_crate_is_not_called_stale() -> None:
    """ "Not built" and "built and old" are different states with different remedies."""
    original = _native._ext
    try:
        _native._ext = None  # type: ignore[assignment]
        assert _native.missing_native_functions() == frozenset()
        _native.assert_native_matches_python()
    finally:
        _native._ext = original


@pytest.mark.skipif(not _native.NATIVE_AVAILABLE, reason="the crate is not built here")
def test_this_machines_build_is_current() -> None:
    """When the extension is present, it must match the crate source beside it."""
    assert _native.missing_native_functions() == frozenset(), (
        "rebuild with `maturin develop` in rust/ — the parity suite is skipping itself"
    )
