"""Human Genome Diversity Project (HGDP) phased-haplotype access.

A thin, named wrapper over :class:`~alleleforge.data.haplotypes.HaplotypePanel`
fixing the source label and the seven HGDP geographic regions. HGDP broadens
ancestry coverage beyond the 1000 Genomes super-populations, which matters for
population-aware off-target safety in under-represented groups.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alleleforge.data.haplotypes import Haplotype, HaplotypePanel
from alleleforge.types.sequence import GenomicInterval

#: HGDP geographic-region labels.
REGIONS = (
    "africa",
    "america",
    "central_south_asia",
    "east_asia",
    "europe",
    "middle_east",
    "oceania",
)


class HGDP:
    """Common-haplotype access over the HGDP panel."""

    source = "hgdp"
    populations = REGIONS

    def __init__(self, panel: HaplotypePanel) -> None:
        """Wrap an already-loaded :class:`HaplotypePanel`."""
        self._panel = panel

    @classmethod
    def from_tsv(cls, path: str | Path) -> HGDP:
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
