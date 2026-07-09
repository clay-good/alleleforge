"""gnomAD population allele-frequency access.

:class:`GnomadDB` answers :meth:`GnomadDB.frequencies` over a genomic interval,
returning per-population minor-allele frequencies used by the Phase 5 off-target
engine to find population variants that create *de novo* PAMs or alter seed-region
mismatches. The default release is **gnomAD v4.1** (see the Phase 3 registry).

Production reads tabix slices of the gnomAD sites VCF; the test path parses a
small plain-text TSV so CI needs no ``pysam`` and no multi-gigabyte file. The TSV
columns are ``chrom pos ref alt af <pop>...`` with ``pos`` **1-based** (matching
the gnomAD VCF), normalized to 0-based on read.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.config import get_settings
from alleleforge.data._io import open_text
from alleleforge.types.sequence import GenomicInterval, canonical_contig

#: gnomAD v4.1 genetic-ancestry group labels.
GNOMAD_POPULATIONS = ("afr", "amr", "asj", "eas", "fin", "nfe", "sas")


class PopulationFrequency(BaseModel):
    """An allele's overall and per-population frequencies at one locus.

    Attributes:
        chrom: Contig name.
        pos: 0-based start coordinate of ``ref``.
        ref: Reference allele.
        alt: Alternate allele.
        overall_af: Overall allele frequency (``AF``).
        populations: Per-population allele frequency, keyed by ancestry label.
    """

    model_config = ConfigDict(frozen=True)

    chrom: str
    pos: int
    ref: str
    alt: str
    overall_af: float
    populations: dict[str, float] = {}

    def max_af(self, populations: Sequence[str] | None = None) -> float:
        """Return the highest frequency across the requested populations.

        Args:
            populations: Ancestry labels to consider; ``None`` considers every
                population plus the overall frequency.
        """
        if populations is None:
            return max([self.overall_af, *self.populations.values()], default=self.overall_af)
        return max((self.populations.get(p, 0.0) for p in populations), default=0.0)

    def exceeds(self, maf: float, populations: Sequence[str] | None = None) -> bool:
        """Return ``True`` if the allele meets ``maf`` in any queried population."""
        return self.max_af(populations) >= maf

    @property
    def variant_key(self) -> str:
        """Return a compact ``chrom:pos:ref>alt`` causal-allele key."""
        return f"{self.chrom}:{self.pos}:{self.ref}>{self.alt}"


class GnomadDB:
    """Indexed access to gnomAD per-population allele frequencies."""

    def __init__(self, records: Iterable[PopulationFrequency]) -> None:
        """Hold ``records`` grouped by contig for interval queries."""
        # Index by canonical contig so a query named in the other style ("chr1"
        # vs "1") still resolves — otherwise a reference-vs-gnomAD naming mismatch
        # silently returns no records and population off-target augmentation is
        # empty (the reference-bias blind spot this module exists to catch).
        self._by_chrom: dict[str, list[PopulationFrequency]] = {}
        for rec in records:
            self._by_chrom.setdefault(canonical_contig(rec.chrom), []).append(rec)
        for recs in self._by_chrom.values():
            recs.sort(key=lambda r: r.pos)

    @classmethod
    def from_sites_tsv(cls, path: str | Path) -> GnomadDB:
        """Parse a ``chrom pos ref alt af <pop>...`` TSV (plain or ``.gz``)."""
        return cls(cls._parse(path))

    @staticmethod
    def _parse(path: str | Path) -> Iterator[PopulationFrequency]:
        """Yield one :class:`PopulationFrequency` per TSV data row."""
        header: list[str] | None = None
        for line in open_text(path):
            if not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if line.startswith("#"):
                header = [c.lstrip("#") for c in cols]
                continue
            if header is None:
                raise ValueError("gnomAD TSV is missing its '#chrom ...' header line")
            row = dict(zip(header, cols, strict=False))
            pops = {p: float(row[p]) for p in header[5:] if row.get(p) not in (None, "", ".")}
            yield PopulationFrequency(
                chrom=row["chrom"],
                pos=int(row["pos"]) - 1,  # gnomAD VCF is 1-based; store 0-based
                ref=row["ref"],
                alt=row["alt"],
                overall_af=float(row["af"]),
                populations=pops,
            )

    def frequencies(
        self,
        interval: GenomicInterval,
        *,
        populations: Sequence[str] | None = None,
        maf: float | None = None,
    ) -> list[PopulationFrequency]:
        """Return allele frequencies overlapping ``interval``.

        Args:
            interval: The query window (0-based half-open).
            populations: Restrict each record's ``populations`` dict to these
                labels; ``None`` keeps every population.
            maf: If given, drop records that do not reach ``maf`` in any queried
                population (the Phase 5 inclusion threshold, default 0.001).

        Returns:
            Matching records, sorted by position.
        """
        out: list[PopulationFrequency] = []
        for rec in self._by_chrom.get(canonical_contig(interval.chrom), ()):
            if not interval.start <= rec.pos < interval.end:
                continue
            if populations is not None:
                rec = rec.model_copy(
                    update={"populations": {p: rec.populations.get(p, 0.0) for p in populations}}
                )
            if maf is not None and not rec.exceeds(maf, populations):
                continue
            out.append(rec)
        return out


def load_default(
    *,
    cache_dir: str | Path | None = None,
    consent: bool = False,
) -> GnomadDB:  # pragma: no cover - requires the fetched release
    """Load the registry-pinned gnomAD release from the user cache.

    Fetches on ``consent=True`` via the default registry; raises otherwise. Not
    exercised in CI, which uses small synthetic TSV fixtures instead.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY

    root = Path(cache_dir) if cache_dir is not None else get_settings().cache_dir / "data"
    path, _ = DEFAULT_REGISTRY.resolve("gnomad", cache_dir=root, consent=consent)
    return GnomadDB.from_sites_tsv(path)
