"""Tests for the top-level package, version, and native bridge.

The ``aforge`` CLI is exercised in ``tests/cli/`` (it requires the optional
``cli`` extra); these tests stay dependency-free.
"""

from __future__ import annotations

from importlib import resources

import alleleforge as af
from alleleforge import _native


def test_version_is_exposed() -> None:
    assert af.__version__ == "0.1.0.dev0"


def test_ships_pep561_py_typed_marker() -> None:
    # The library is mypy --strict clean; the PEP 561 marker is what makes those
    # types visible to a downstream type-checker. Without it the marker can be
    # dropped silently (it has no functional consumer), so guard it explicitly.
    marker = resources.files("alleleforge").joinpath("py.typed")
    assert marker.is_file()


def test_bundles_runtime_data_files() -> None:
    # The registry, benchmark, and web server load these via package paths at runtime.
    #
    # What this proves and what it does not: `resources.files` resolves to the source
    # tree under a development install, so this checks the files exist in the repository
    # and are reachable by the path the code uses. It does not open a wheel, and the
    # comment here used to claim it caught a packaging change that "would break the
    # installed wheel" — it cannot see one. The wheel was checked by hand instead
    # (2026-09-07: py.typed, 17 cards, 6 splits, 3 frontend files and the CFD matrix all
    # present, and the package imports and resolves them from the wheel's own contents).
    # Building a wheel here would cost the suite a minute per run to re-prove something
    # the build backend does by default: hatchling packages `src/alleleforge` wholesale,
    # so dropping an asset takes a deliberate exclude rather than an oversight.
    cards = resources.files("alleleforge").joinpath("model_zoo", "cards")
    splits = resources.files("alleleforge").joinpath("benchmark", "splits")
    frontend = resources.files("alleleforge").joinpath("web", "frontend", "index.html")
    assert any(p.name.endswith(".yaml") for p in cards.iterdir())
    assert any(p.name.endswith(".json") for p in splits.iterdir())
    assert frontend.is_file()


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
