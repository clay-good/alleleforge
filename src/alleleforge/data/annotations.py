"""GENCODE gene models and ENCODE chromatin-track signal lookups.

Two per-locus annotation sources used by later phases:

* :class:`GeneModels` parses GENCODE ``gene`` features from a GTF and answers
  :meth:`GeneModels.genes_in` / :meth:`GeneModels.gene`, feeding transcript
  selection in the variant resolver (Phase 4).
* :class:`EncodeTracks` parses bedGraph signal tracks (DNase/ATAC/CTCF/H3K27ac)
  and answers :meth:`EncodeTracks.signal` as an overlap-weighted mean, feeding
  chromatin-aware prime-editing efficiency (ePRIDICT, Phase 9).

Both parse plain-text (optionally gzipped) fixtures so CI needs no genome-scale
files. GTF coordinates are 1-based inclusive (normalized to 0-based on read);
bedGraph coordinates are already 0-based half-open.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.data._io import open_text
from alleleforge.types.sequence import GenomicInterval, Strand

_ATTR_RE = re.compile(r'(\w+) "([^"]*)"')


class Gene(BaseModel):
    """A GENCODE gene model.

    Attributes:
        gene_id: Ensembl gene identifier (e.g. ``ENSG00000119866``).
        symbol: HGNC gene symbol (e.g. ``BCL11A``).
        gene_type: Biotype (e.g. ``protein_coding``).
        interval: The gene's genomic span (0-based half-open, strand-aware).
    """

    model_config = ConfigDict(frozen=True)

    gene_id: str
    symbol: str
    gene_type: str
    interval: GenomicInterval


class GeneModels:
    """Queryable GENCODE gene models."""

    def __init__(self, genes: Iterable[Gene]) -> None:
        """Index ``genes`` by symbol and by contig."""
        self._genes = list(genes)
        self._by_symbol: dict[str, list[Gene]] = defaultdict(list)
        self._by_chrom: dict[str, list[Gene]] = defaultdict(list)
        for gene in self._genes:
            self._by_symbol[gene.symbol.upper()].append(gene)
            self._by_chrom[gene.interval.chrom].append(gene)

    @classmethod
    def from_gtf(cls, path: str | Path) -> GeneModels:
        """Parse ``gene`` features from a GENCODE GTF (plain or ``.gz``)."""
        return cls(cls._parse(path))

    @staticmethod
    def _parse(path: str | Path) -> Iterator[Gene]:
        """Yield one :class:`Gene` per ``gene`` feature line."""
        for line in open_text(path):
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 9 or cols[2] != "gene":
                continue
            attrs = dict(_ATTR_RE.findall(cols[8]))
            interval = GenomicInterval(
                chrom=cols[0],
                start=int(cols[3]) - 1,  # GTF is 1-based inclusive
                end=int(cols[4]),
                strand=Strand.PLUS if cols[6] == "+" else Strand.MINUS,
            )
            yield Gene(
                gene_id=attrs.get("gene_id", ""),
                symbol=attrs.get("gene_name", ""),
                gene_type=attrs.get("gene_type", ""),
                interval=interval,
            )

    def __len__(self) -> int:
        """Return the number of parsed genes."""
        return len(self._genes)

    def gene(self, symbol: str) -> Gene:
        """Return the single gene with ``symbol``.

        Raises:
            KeyError: If no gene has that symbol.
            ValueError: If more than one gene shares the symbol.
        """
        matches = self._by_symbol.get(symbol.upper(), [])
        if not matches:
            raise KeyError(f"no gene named {symbol!r}")
        if len(matches) > 1:
            raise ValueError(f"{symbol!r} is ambiguous: {len(matches)} gene models")
        return matches[0]

    def genes(self, symbol: str) -> list[Gene]:
        """Return all gene models with ``symbol`` (case-insensitive)."""
        return list(self._by_symbol.get(symbol.upper(), ()))

    def genes_in(self, interval: GenomicInterval) -> list[Gene]:
        """Return genes overlapping ``interval``, sorted by start."""
        hits = [g for g in self._by_chrom.get(interval.chrom, ()) if g.interval.overlaps(interval)]
        hits.sort(key=lambda g: g.interval.start)
        return hits


class _Segment(BaseModel):
    """A single bedGraph signal segment (0-based half-open)."""

    model_config = ConfigDict(frozen=True)

    start: int
    end: int
    value: float


class EncodeTracks:
    """Per-locus signal lookups over ENCODE bedGraph tracks.

    Fixture format: ``track chrom start end value`` (0-based half-open).
    """

    def __init__(self, segments: dict[tuple[str, str], list[_Segment]]) -> None:
        """Hold pre-grouped ``(track, chrom) -> segments`` lists (sorted)."""
        self._segments = segments

    @classmethod
    def from_bedgraph(cls, path: str | Path) -> EncodeTracks:
        """Parse a ``track chrom start end value`` bedGraph (plain or ``.gz``)."""
        grouped: dict[tuple[str, str], list[_Segment]] = defaultdict(list)
        for line in open_text(path):
            if line.startswith(("#", "track", "browser")) or not line.strip():
                continue
            track, chrom, start, end, value = line.rstrip("\n").split("\t")
            grouped[(track, chrom)].append(
                _Segment(start=int(start), end=int(end), value=float(value))
            )
        for segs in grouped.values():
            segs.sort(key=lambda s: s.start)
        return cls(dict(grouped))

    @property
    def tracks(self) -> tuple[str, ...]:
        """Return the distinct track names, sorted."""
        return tuple(sorted({track for track, _ in self._segments}))

    def signal(self, track: str, interval: GenomicInterval) -> float:
        """Return the overlap-weighted mean signal of ``track`` over ``interval``.

        Returns ``0.0`` when the track has no coverage over the interval.

        Raises:
            KeyError: If ``track`` is not present at all.
        """
        if track not in self.tracks:
            raise KeyError(f"unknown track {track!r}; known: {self.tracks}")
        total = 0.0
        covered = 0
        for seg in self._segments.get((track, interval.chrom), ()):
            lo = max(seg.start, interval.start)
            hi = min(seg.end, interval.end)
            if hi > lo:
                total += seg.value * (hi - lo)
                covered += hi - lo
        return total / covered if covered else 0.0
