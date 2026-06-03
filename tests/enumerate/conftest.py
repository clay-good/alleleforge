"""Shared fixtures for Phase 7 enumeration/design tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome

#: A 20-nt protospacer with no GG and no CC, so the only NGG/CCN PAM in a test
#: contig is the one deliberately appended — and it is not a reverse-complement
#: palindrome, so plus and minus guides are distinguishable.
SPACER = "ACGTAACGTTACGTAACGTT"
PAD = "T" * 15


@pytest.fixture
def make_reference(tmp_path: Path) -> Callable[[dict[str, str]], ReferenceGenome]:
    """Return a factory building a :class:`ReferenceGenome` from inline contigs."""
    counter = {"n": 0}

    def _make(contigs: dict[str, str]) -> ReferenceGenome:
        counter["n"] += 1
        fasta = tmp_path / f"ref{counter['n']}.fa"
        fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
        return ReferenceGenome(fasta, build="hg38")

    return _make
