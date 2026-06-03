"""Fixtures for the off-target tests: synthetic references and a canonical spacer.

Synthetic contigs are written to a temp FASTA and opened as a real
:class:`ReferenceGenome`, so the engine runs end to end against actual sequence
without any genome-scale file.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome

#: A 20-nt SpCas9 spacer with no internal ``NRG`` PAM (so it never self-matches).
SPACER = "GACCATGCAACCTTGAACGT"

#: Padding made of a base absent from any PAM's 3rd position keeps synthetic
#: contigs free of spurious PAM anchors.
PAD = "T" * 10


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
