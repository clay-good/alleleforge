"""1000 Genomes phased-haplotype access (phase 3, high-coverage).

A thin, named wrapper over :class:`~alleleforge.data.haplotypes.HaplotypePanel`
fixing the source label and the five 1000 Genomes super-populations. Used by the
Phase 5 off-target engine to enumerate common haplotypes for haplotype-aware
search.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alleleforge.data.haplotypes import Haplotype, HaplotypePanel
from alleleforge.types.sequence import GenomicInterval

#: 1000 Genomes super-population labels.
SUPERPOPULATIONS = ("AFR", "AMR", "EAS", "EUR", "SAS")


class ThousandGenomes:
    """Common-haplotype access over the 1000 Genomes high-coverage panel."""

    source = "1000g"
    populations = SUPERPOPULATIONS

    def __init__(self, panel: HaplotypePanel) -> None:
        """Wrap an already-loaded :class:`HaplotypePanel`."""
        self._panel = panel

    @classmethod
    def from_tsv(cls, path: str | Path) -> ThousandGenomes:
        """Load the panel from a phased-haplotype TSV (plain or ``.gz``)."""
        return cls(HaplotypePanel.from_tsv(path, source=cls.source))

    def common_haplotypes(
        self,
        interval: GenomicInterval,
        *,
        min_freq: float = 0.001,
        populations: Sequence[str] | None = None,
        include_reference: bool = False,
    ) -> list[Haplotype]:
        """Return common haplotypes overlapping ``interval`` (see the panel)."""
        return self._panel.common_haplotypes(
            interval,
            min_freq=min_freq,
            populations=populations,
            include_reference=include_reference,
        )
