"""Tests for GENCODE gene models and ENCODE track signal lookups."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.annotations import EncodeTracks, GeneModels
from alleleforge.types.sequence import GenomicInterval, Strand


def _interval(start: int, end: int, chrom: str = "chr2") -> GenomicInterval:
    return GenomicInterval(chrom=chrom, start=start, end=end, strand=Strand.PLUS)


def test_gene_lookup_and_coordinate_conversion(gencode_gtf: Path) -> None:
    models = GeneModels.from_gtf(gencode_gtf)
    bcl11a = models.gene("BCL11A")
    assert bcl11a.gene_id == "ENSG00000119866"
    assert bcl11a.gene_type == "protein_coding"
    assert bcl11a.interval.start == 60000  # 1-based 60001 -> 0-based
    assert bcl11a.interval.end == 60600


def test_gene_skips_non_gene_features(gencode_gtf: Path) -> None:
    models = GeneModels.from_gtf(gencode_gtf)
    assert len(models) == 3  # the 'transcript' line is ignored


def test_gene_is_case_insensitive(gencode_gtf: Path) -> None:
    models = GeneModels.from_gtf(gencode_gtf)
    assert models.gene("hbb").interval.strand is Strand.MINUS


def test_unknown_gene_raises(gencode_gtf: Path) -> None:
    models = GeneModels.from_gtf(gencode_gtf)
    with pytest.raises(KeyError, match="no gene named"):
        models.gene("NOPE")


def test_genes_in_region(gencode_gtf: Path) -> None:
    models = GeneModels.from_gtf(gencode_gtf)
    hits = models.genes_in(_interval(5225000, 5226200, chrom="chr11"))
    assert sorted(g.symbol for g in hits) == ["HBB", "HBD"]


def test_signal_overlap_weighted_mean(encode_bedgraph: Path) -> None:
    tracks = EncodeTracks.from_bedgraph(encode_bedgraph)
    # interval [60000, 60400): 200 bp at 5.0 then 200 bp at 1.0 -> mean 3.0
    assert tracks.signal("DNase", _interval(60000, 60400)) == pytest.approx(3.0)
    # H3K27ac is flat 3.0 across the gene
    assert tracks.signal("H3K27ac", _interval(60100, 60500)) == pytest.approx(3.0)


def test_signal_partial_coverage(encode_bedgraph: Path) -> None:
    tracks = EncodeTracks.from_bedgraph(encode_bedgraph)
    # CTCF covers only [60100, 60150); querying [60100, 60150) -> 8.0
    assert tracks.signal("CTCF", _interval(60100, 60150)) == pytest.approx(8.0)


def test_signal_no_coverage_is_zero(encode_bedgraph: Path) -> None:
    tracks = EncodeTracks.from_bedgraph(encode_bedgraph)
    assert tracks.signal("DNase", _interval(80000, 80100)) == 0.0


def test_tracks_listed(encode_bedgraph: Path) -> None:
    tracks = EncodeTracks.from_bedgraph(encode_bedgraph)
    assert tracks.tracks == ("CTCF", "DNase", "H3K27ac")


def test_unknown_track_raises(encode_bedgraph: Path) -> None:
    tracks = EncodeTracks.from_bedgraph(encode_bedgraph)
    with pytest.raises(KeyError, match="unknown track"):
        tracks.signal("ATAC", _interval(60000, 60100))


def test_ambiguous_gene_symbol(tmp_path: Path) -> None:
    gtf = tmp_path / "dup.gtf"
    gtf.write_text(
        'chr1\tX\tgene\t1\t100\t.\t+\t.\tgene_id "A"; gene_name "DUP"; gene_type "x";\n'
        'chr2\tX\tgene\t1\t100\t.\t+\t.\tgene_id "B"; gene_name "DUP"; gene_type "x";\n'
    )
    models = GeneModels.from_gtf(gtf)
    assert len(models.genes("DUP")) == 2
    with pytest.raises(ValueError, match="ambiguous"):
        models.gene("DUP")
