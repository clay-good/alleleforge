"""dbSNP rsID <-> locus resolution (build 156+).

:class:`DbSnpDB` maps a dbSNP ``rsID`` to its normalized variant and back,
backing the variant resolver's rsID input form (Phase 4). Production reads tabix
slices of the dbSNP VCF; the test path parses a small plain-text TSV with columns
``rsid chrom pos ref alt`` (``pos`` **1-based**, normalized to 0-based on read).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

from alleleforge.data._io import open_text
from alleleforge.types.sequence import GenomicInterval
from alleleforge.types.variant import DbSnpId, Variant


class DbSnpDB:
    """Bidirectional rsID <-> variant lookup."""

    def __init__(self, variants: Iterable[Variant]) -> None:
        """Index ``variants`` (each carrying an ``rsid``) by rsID and by contig."""
        self._by_rsid: dict[str, Variant] = {}
        self._by_chrom: dict[str, list[Variant]] = defaultdict(list)
        for var in variants:
            if var.rsid is None:
                raise ValueError(f"dbSNP variant {var} has no rsid")
            self._by_rsid[var.rsid.value] = var
            self._by_chrom[var.chrom].append(var)
        for recs in self._by_chrom.values():
            recs.sort(key=lambda v: v.pos)

    @classmethod
    def from_tsv(
        cls, path: str | Path, *, add_chr_prefix: bool = True, assembly: str | None = None
    ) -> DbSnpDB:
        """Parse an ``rsid chrom pos ref alt`` TSV (plain or ``.gz``).

        ``assembly`` records the release's native assembly on each variant's
        ``source_assembly`` so a requested build can be reconciled against it; it
        is left unknown (``None``) when the caller does not state it, rather than
        assuming the default build.
        """
        return cls(cls._parse(path, add_chr_prefix=add_chr_prefix, assembly=assembly))

    @staticmethod
    def _parse(
        path: str | Path, *, add_chr_prefix: bool, assembly: str | None = None
    ) -> Iterator[Variant]:
        """Yield one normalized :class:`Variant` per TSV data row."""
        header: list[str] | None = None
        for line in open_text(path):
            if not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if line.startswith("#"):
                header = [c.lstrip("#") for c in cols]
                continue
            if header is None:
                raise ValueError("dbSNP TSV is missing its '#rsid ...' header line")
            row = dict(zip(header, cols, strict=False))
            chrom = row["chrom"]
            if add_chr_prefix and not chrom.lower().startswith("chr"):
                chrom = f"chr{chrom}"
            yield Variant(
                chrom=chrom,
                pos=int(row["pos"]) - 1,  # dbSNP VCF is 1-based; store 0-based
                ref=row["ref"],
                alt=row["alt"],
                source_assembly=assembly,
                rsid=DbSnpId(value=row["rsid"]),
            ).normalized()

    def __len__(self) -> int:
        """Return the number of indexed rsIDs."""
        return len(self._by_rsid)

    def locus(self, rsid: str | DbSnpId) -> Variant:
        """Return the variant for ``rsid``.

        Raises:
            KeyError: If the rsID is not present.
        """
        key = DbSnpId(value=str(rsid)).value
        if key not in self._by_rsid:
            raise KeyError(f"no dbSNP record for {key}")
        return self._by_rsid[key]

    def rsids_at(self, interval: GenomicInterval) -> list[DbSnpId]:
        """Return rsIDs whose variant start falls within ``interval``."""
        return [
            v.rsid
            for v in self._by_chrom.get(interval.chrom, ())
            if v.rsid is not None and interval.start <= v.pos < interval.end
        ]
