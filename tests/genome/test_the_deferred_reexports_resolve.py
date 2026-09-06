"""The lazy re-export path was live in production and run by no test.

`alleleforge.genome` defers four names to `alleleforge.genome.reference` through PEP 562,
so importing the package does not pull in `pyfaidx`. The whole `__getattr__` body was
uncovered: every test reaches `ReferenceGenome` through
`from alleleforge.genome.reference import ...`, the eager path, while the documented
`from alleleforge.genome import ReferenceGenome` — the one the deferral exists to keep
working — was exercised nowhere.

A typo in `_LAZY_FROM_REFERENCE`, or a name moved out of `reference.py`, would surface at
a user's first attribute access rather than in the suite. And the tuple and `__all__` are
two hand-written lists of the same names, which this session has watched drift twice.
"""

from __future__ import annotations

import importlib

import pytest

import alleleforge.genome as genome
from alleleforge.genome import _LAZY_FROM_REFERENCE


def test_every_deferred_name_resolves_to_the_real_object() -> None:
    reference = importlib.import_module("alleleforge.genome.reference")
    for name in _LAZY_FROM_REFERENCE:
        assert getattr(genome, name) is getattr(reference, name), name


def test_an_unknown_name_still_raises_attribute_error() -> None:
    """The `__getattr__` fallback: a missing name must not resolve to something."""
    with pytest.raises(AttributeError, match="has no attribute 'NoSuchName'"):
        genome.NoSuchName  # noqa: B018


def test_the_deferred_names_are_exported() -> None:
    """Two hand-written lists of the same names; a deferred name absent from `__all__`
    is invisible to `from ... import *` and to anything reading the public surface."""
    missing = sorted(set(_LAZY_FROM_REFERENCE) - set(genome.__all__))
    assert not missing, f"deferred but not exported: {missing}"
