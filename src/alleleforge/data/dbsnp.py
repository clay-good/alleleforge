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

from alleleforge.data._io import is_sequence_allele, open_text
from alleleforge.types.sequence import (
    GenomicInterval,
    canonical_contig,
    contig_from_refseq,
)
from alleleforge.types.variant import DbSnpId, Variant

#: The columns every data row is read through. Checked at the header rather than at the
#: first row: a TSV with a header of some *other* schema — a gnomAD frequency table handed
#: to `--dbsnp`, one flag over — reached `row["rsid"]` and surfaced as the bare `'rsid'`,
#: which names neither the file, the schema it has, nor the schema it needs. gnomAD's
#: reader has checked this since it shipped; this one had not.
_CORE_COLUMNS = ("rsid", "chrom", "pos", "ref", "alt")


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
            # Key by the canonical contig so a bare-named ("2") interval query still
            # finds a chr-named ("chr2") record — the reference-vs-source naming blind
            # spot the sibling loaders (gnomad/clinvar/haplotype) all reconcile.
            self._by_chrom[canonical_contig(var.chrom)].append(var)
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

    @classmethod
    def load(cls, path: str | Path, *, assembly: str | None = None) -> DbSnpDB:
        """Read either form dbSNP comes in, deciding by content rather than by name.

        Sniffed, not switched on the extension, because **the file NCBI publishes is
        called ``GCF_000001405.40.gz``** — nothing in that name says VCF. A reader that
        dispatched on ``.vcf`` would reject the only artifact upstream actually serves,
        which is how the project came to tell callers to convert it by hand.

        Dispatch is on the *positive* VCF signal only: a first line of
        ``##fileformat=VCF`` goes to :meth:`from_vcf`, and **everything else goes to**
        :meth:`from_tsv`. That asymmetry is deliberate. An earlier draft raised its own
        "neither a VCF nor a TSV" error, which intercepted a TSV with the wrong columns
        and replaced `from_tsv`'s diagnosis — "Expected a tab-separated header of: … —
        found: …" — with a vaguer one. Two tests caught it. A reader whose file is nearly
        right needs the column-by-column comparison, not a restatement of the two
        formats, so the detailed refusal is left where it already lived.
        """
        for line in open_text(path):
            if not line.strip():
                continue
            if line.startswith("##fileformat=VCF"):
                return cls.from_vcf(path, assembly=assembly)
            break
        return cls.from_tsv(path, assembly=assembly)

    @classmethod
    def from_vcf(cls, path: str | Path, *, assembly: str | None = None) -> DbSnpDB:
        """Parse dbSNP's own VCF release (plain or ``.gz``) into a :class:`DbSnpDB`.

        This exists because the artifact NCBI publishes and the artifact this class could
        read were different files. `from_tsv` wants an ``rsid chrom pos ref alt`` table,
        and the resolver's own error message told callers to produce one — from a VCF
        nothing here could open. So the one dataset the registry describes as fetchable-
        in-principle was unusable without a conversion the project neither performed nor
        documented.

        Two things about dbSNP's VCF that a generic reader gets wrong:

        * **every contig is a versioned RefSeq accession** (``NC_000001.11``), not
          ``chr1``, so a reader that only strips a ``chr`` prefix produces contigs no
          reference has. Unplaced scaffolds and patches (``NT_``/``NW_``) are skipped
          rather than refused — a whole-genome release carries thousands and none of them
          is an error;
        * **ALT is multi-allelic** (``A,C``). One VCF row is several variants, so each
          allele is yielded separately — in a 400-row slice of b156, 537 alleles come
          from 363 rsIDs, so a reader that kept one per row would drop a quarter of them.

        One pre-existing limitation this reader is the first to make reachable:
        :meth:`locus` indexes by rsID in a plain dict, so for a multi-allelic site it
        answers with the *last* allele read, while :meth:`rsids_at` sees all of them. The
        TSV path could always hit this by listing an rsID twice; nothing produced such
        input before. Pinned in
        ``tests/data/test_dbsnp_reads_the_vcf_that_ncbi_publishes.py`` so it is a known
        shape rather than a surprise, and left alone here because widening `locus` to
        return every allele changes a public return type.

        Args:
            path: Path to a dbSNP VCF release.
            assembly: The release's native assembly, recorded on each variant's
                ``source_assembly``. Left unknown when not stated rather than assuming
                the default build.

        Returns:
            A queryable :class:`DbSnpDB`.
        """
        return cls(cls._parse_vcf(path, assembly=assembly))

    @staticmethod
    def _parse_vcf(path: str | Path, *, assembly: str | None = None) -> Iterator[Variant]:
        """Yield one :class:`Variant` per usable (row, ALT) pair of a dbSNP VCF."""
        for line in open_text(path):
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            accession, pos, rsid, ref, alts = cols[0], cols[1], cols[2], cols[3], cols[4]
            # No rs number means no dbSNP identity, which is the only key this class
            # indexes by; such a row belongs to a different database.
            if not rsid.startswith("rs"):
                continue
            chrom = contig_from_refseq(accession)
            if chrom is None:
                continue  # unplaced scaffold or patch contig
            for alt in alts.split(","):
                if not is_sequence_allele(ref, alt):
                    continue  # symbolic or spanning-deletion allele
                yield Variant(
                    chrom=chrom,
                    pos=int(pos) - 1,  # dbSNP VCF is 1-based; store 0-based
                    ref=ref,
                    alt=alt,
                    source_assembly=assembly,
                    rsid=DbSnpId(value=rsid),
                ).normalized()

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
                missing = [c for c in _CORE_COLUMNS if c not in header]
                if missing:
                    raise ValueError(
                        f"dbSNP TSV header is missing {', '.join(missing)}. Expected a "
                        f"tab-separated header of: {'  '.join(_CORE_COLUMNS)} — found: "
                        f"{'  '.join(header)}"
                    )
                continue
            if header is None:
                raise ValueError("dbSNP TSV is missing its '#rsid ...' header line")
            row = dict(zip(header, cols, strict=False))
            # Skip a symbolic/spanning-deletion allele rather than letting it reach the
            # allele validator and abort the whole file (mirrors clinvar/gnomad).
            if not is_sequence_allele(row["ref"], row["alt"]):
                continue
            chrom = row["chrom"]
            if add_chr_prefix and not chrom.lower().startswith("chr"):
                # hg38 spells the mitochondrion "chrM", not "chrMT" — mirror clinvar's
                # _with_chr so a bare "MT" rsID lands on the reference's contig.
                chrom = "chrM" if chrom in {"MT", "M"} else f"chr{chrom}"
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
            for v in self._by_chrom.get(canonical_contig(interval.chrom), ())
            if v.rsid is not None and interval.start <= v.pos < interval.end
        ]
