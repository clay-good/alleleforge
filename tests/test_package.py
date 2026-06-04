"""Tests for the top-level package, version, and native bridge.

The ``aforge`` CLI is exercised in ``tests/cli/`` (it requires the optional
``cli`` extra); these tests stay dependency-free.
"""

from __future__ import annotations

import alleleforge as af
from alleleforge import _native


def test_version_is_exposed() -> None:
    assert af.__version__ == "0.1.0.dev0"


def test_types_reexported() -> None:
    assert hasattr(af, "types")
    assert af.types.Strand.PLUS.value == "+"


def test_settings_reexported() -> None:
    assert af.get_settings().seed == 20240501


def test_native_available_is_bool() -> None:
    assert isinstance(_native.NATIVE_AVAILABLE, bool)


def test_native_version_consistency() -> None:
    # When the extension is built its version must match; when absent it is None.
    nv = _native.native_version()
    if nv is not None:
        assert nv == af.__version__
    _native.assert_native_matches_python()  # no-op when not built
