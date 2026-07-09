"""Phased-haplotype panels shared by the 1000 Genomes and HGDP sources.

A :class:`HaplotypePanel` enumerates the **common haplotypes** spanning a query
interval, each carried at some per-population frequency. The Phase 5 off-target
engine walks these haplotypes (in the Rust ``haplotype.rs`` kernel) so that an
off-target created only on a common non-reference haplotype is still nominated,
and is reported with the populations that carry it.

Production builds these from phased VCFs; the test path parses a small plain-text
TSV. Each row is one ``(haplotype, population)`` observation:

``hap_id  chrom  start  end  population  frequency  variants``

where ``start``/``end`` are 0-based half-open, ``variants`` is a comma-separated
list of ``chrom:pos:ref>alt`` (0-based ``pos``) or empty for the reference
haplotype.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.data._io import open_text
from alleleforge.types.sequence import GenomicInterval, Strand, canonical_contig
from alleleforge.types.variant import Variant


class Haplotype(BaseModel):
    """A common haplotype over a window and the populations carrying it.

    Attributes:
        hap_id: Panel-local haplotype identifier.
        interval: The window the haplotype is defined over (0-based half-open).
        variants: The non-reference alleles the haplotype carries, in order.
        frequencies: Per-population frequency of the haplotype.
        source: The panel that produced it (e.g. ``"1000g"``, ``"hgdp"``).
    """

    model_config = ConfigDict(frozen=True)

    hap_id: str
    interval: GenomicInterval
    variants: tuple[Variant, ...]
    frequencies: dict[str, float]
    source: str

    @property
    def is_reference(self) -> bool:
        """Return ``True`` if the haplotype carries no non-reference allele."""
        return len(self.variants) == 0

    @property
    def populations(self) -> tuple[str, ...]:
        """Return the populations that carry this haplotype (frequency > 0)."""
        return tuple(sorted(p for p, f in self.frequencies.items() if f > 0.0))

    def max_freq(self, populations: Sequence[str] | None = None) -> float:
        """Return the highest frequency over the requested populations."""
        if populations is None:
            return max(self.frequencies.values(), default=0.0)
        return max((self.frequencies.get(p, 0.0) for p in populations), default=0.0)


def _parse_variants(field: str) -> tuple[Variant, ...]:
    """Parse a ``chrom:pos:ref>alt,...`` field (0-based pos) into variants."""
    field = field.strip()
    if not field or field == ".":
        return ()
    variants: list[Variant] = []
    for token in field.split(","):
        chrom, pos_s, alleles = token.split(":")
        ref, alt = alleles.split(">")
        variants.append(Variant(chrom=chrom, pos=int(pos_s), ref=ref, alt=alt).normalized())
    return tuple(variants)


class HaplotypePanel:
    """A queryable panel of common phased haplotypes."""

    def __init__(self, haplotypes: Iterable[Haplotype], *, source: str) -> None:
        """Hold ``haplotypes`` grouped by contig; record the panel ``source``."""
        self.source = source
        # Index by canonical contig so a query named in the other style ("chr1"
        # vs "1") still resolves — a panel built from a bare-named 1000G/HGDP VCF
        # queried with a chr-named hg38 interval would otherwise miss its bucket
        # and silently return no haplotypes, yielding an empty haplotype-aware
        # off-target pass (the reference-bias blind spot this module exists to
        # catch). `overlaps` is already naming-aware, but the bucket lookup below
        # runs first and never reached it.
        self._by_chrom: dict[str, list[Haplotype]] = defaultdict(list)
        for hap in haplotypes:
            self._by_chrom[canonical_contig(hap.interval.chrom)].append(hap)

    @classmethod
    def from_tsv(cls, path: str | Path, *, source: str) -> HaplotypePanel:
        """Parse a phased-haplotype TSV (plain or ``.gz``) into a panel.

        Each ``(haplotype, population)`` row contributes one frequency; rows
        sharing a ``hap_id`` and span are merged into a single haplotype whose
        per-population frequencies are accumulated in encounter order.
        """
        intervals: dict[tuple[str, str], GenomicInterval] = {}
        variants: dict[tuple[str, str], tuple[Variant, ...]] = {}
        freqs: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        header: list[str] | None = None
        for line in open_text(path):
            if not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if line.startswith("#"):
                header = [c.lstrip("#") for c in cols]
                continue
            if header is None:
                raise ValueError("haplotype TSV is missing its '#hap_id ...' header line")
            row = dict(zip(header, cols, strict=False))
            start, end = int(row["start"]), int(row["end"])
            key = (row["hap_id"], f"{row['chrom']}:{start}-{end}")
            if key not in intervals:
                intervals[key] = GenomicInterval(
                    chrom=row["chrom"], start=start, end=end, strand=Strand.PLUS
                )
                variants[key] = _parse_variants(row.get("variants", ""))
            freqs[key][row["population"]] = float(row["frequency"])
        haplotypes = [
            Haplotype(
                hap_id=key[0],
                interval=intervals[key],
                variants=variants[key],
                frequencies=freqs[key],
                source=source,
            )
            for key in intervals
        ]
        return cls(haplotypes, source=source)

    def common_haplotypes(
        self,
        interval: GenomicInterval,
        *,
        min_freq: float = 0.001,
        populations: Sequence[str] | None = None,
        include_reference: bool = False,
    ) -> list[Haplotype]:
        """Return haplotypes overlapping ``interval`` at frequency >= ``min_freq``.

        Args:
            interval: The query window (0-based half-open).
            min_freq: Minimum per-population frequency to be "common".
            populations: Restrict the frequency test to these populations.
            include_reference: Keep the reference (no-variant) haplotype too.

        Returns:
            Matching haplotypes, sorted by descending max frequency.
        """
        out = [
            hap
            for hap in self._by_chrom.get(canonical_contig(interval.chrom), ())
            if hap.interval.overlaps(interval)
            and (include_reference or not hap.is_reference)
            and hap.max_freq(populations) >= min_freq
        ]
        out.sort(key=lambda h: h.max_freq(populations), reverse=True)
        return out
