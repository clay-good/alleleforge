"""Three loaders promise coordinate order, and every fixture handed them sorted input.

`genes_in` is documented "sorted by start", `frequencies` "sorted by position", and
`rsids_at` reads an index the loader sorts. A statement-deletion sweep removed each
`sort(...)` with the whole suite green — because every fixture in the suite lists its
records in coordinate order already, so sorted input stays sorted whether or not
anything sorts it.

Real sources are not sorted. A gnomAD sites TSV concatenated from two shards, a VCF a
user filtered and re-joined, a GENCODE GTF where one gene's records interleave with its
neighbour's — all of them arrive out of order, and every one is a supported input. The
result is order-dependent output: this project treats a byte-reproducible artifact as a
contract, and a gene list or a frequency list whose order follows the input file's is
not reproducible across two equivalent sources.

`EncodeTracks` sorts its segments in both constructors and those two are **inert**:
`signal` is an overlap-weighted sum over every overlapping segment, so its value does
not depend on their order (beyond float-summation order, which no assertion at these
magnitudes can see). Nothing else reads the segment list. Recorded rather than carried,
with the order-independence of `signal` pinned below so the claim is checked rather
than asserted.

Each fixture here is deliberately shuffled, which is the whole content of this file:
the sorted one proves nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.annotations import EncodeTracks, Gene, GeneModels
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import DbSnpId, Variant

_WINDOW = GenomicInterval(chrom="chr1", start=0, end=10_000, strand=Strand.PLUS)
_STARTS = (900, 100, 500, 300, 700)


def _gene(start: int) -> Gene:
    return Gene(
        gene_id=f"ENSG{start:011d}",
        symbol=f"G{start}",
        gene_type="protein_coding",
        interval=GenomicInterval(chrom="chr1", start=start, end=start + 50, strand=Strand.PLUS),
    )


def test_the_fixture_starts_are_not_already_in_order() -> None:
    """The premise of every check in this file."""
    assert list(_STARTS) != sorted(_STARTS)


def test_genes_come_back_in_coordinate_order() -> None:
    models = GeneModels(_gene(s) for s in _STARTS)
    hits = models.genes_in(_WINDOW)
    assert [g.interval.start for g in hits] == sorted(_STARTS)


def test_population_frequencies_come_back_in_coordinate_order() -> None:
    db = GnomadDB(
        PopulationFrequency(chrom="chr1", pos=s, ref="A", alt="C", overall_af=0.01) for s in _STARTS
    )
    hits = db.frequencies(_WINDOW)
    assert [r.pos for r in hits] == sorted(_STARTS)


def test_rsids_come_back_in_coordinate_order() -> None:
    db = DbSnpDB(
        Variant(chrom="chr1", pos=s, ref="A", alt="C", rsid=DbSnpId(value=f"rs{s}"))
        for s in _STARTS
    )
    found = db.rsids_at(_WINDOW)
    assert [int(str(r.value)[2:]) for r in found] == sorted(_STARTS)


def test_a_tracks_signal_does_not_depend_on_segment_order(tmp_path: Path) -> None:
    """The premise for calling the two segment sorts inert, checked not assumed.

    A bedGraph is written per track, not per coordinate, so this is the shuffled input
    a real deployment hands in — and the signal it reports must be the same either way.
    """
    path = tmp_path / "shuffled.bedgraph"
    path.write_text("".join(f"atac\tchr1\t{s}\t{s + 50}\t{float(s)}\n" for s in _STARTS))
    tracks = EncodeTracks.from_bedgraph(path)
    for start in _STARTS:
        window = GenomicInterval(chrom="chr1", start=start, end=start + 50, strand=Strand.PLUS)
        assert tracks.signal("atac", window) == pytest.approx(float(start)), start
