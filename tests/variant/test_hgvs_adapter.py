"""Tests for the dependency-free genomic HGVS parser and adapter."""

from __future__ import annotations

import importlib.util

import pytest

from alleleforge.variant.hgvs_adapter import (
    HgvsAdapter,
    HgvsLibraryProjector,
    HgvsOp,
    parse_genomic_hgvs,
)


def test_parse_substitution_with_refseq_prefix() -> None:
    p = parse_genomic_hgvs("NC_000002.12:g.60100A>T")
    assert p.reference == "NC_000002.12"
    assert p.op is HgvsOp.SUB
    assert p.start == 60099 and p.end == 60100  # 1-based 60100 -> 0-based
    assert p.ref_bases == "A" and p.alt_bases == "T"


def test_parse_deletion_range() -> None:
    p = parse_genomic_hgvs("chr2:g.100_102del")
    assert p.op is HgvsOp.DEL
    assert p.start == 99 and p.end == 102  # spans 3 bases
    assert p.ref_bases is None  # not stated; filled from the reference


def test_parse_insertion() -> None:
    p = parse_genomic_hgvs("chr2:g.100_101insAC")
    assert p.op is HgvsOp.INS
    assert p.start == p.end == 100  # zero-width, anchored before the right base
    assert p.alt_bases == "AC"


def test_parse_delins() -> None:
    p = parse_genomic_hgvs("g.100_102delinsAA")
    assert p.op is HgvsOp.DELINS
    assert p.alt_bases == "AA"


def test_non_genomic_rejected() -> None:
    with pytest.raises(ValueError, match="not a genomic"):
        parse_genomic_hgvs("NM_000518.5:c.20A>T")


def test_insertion_requires_bases() -> None:
    with pytest.raises(ValueError, match="inserted bases"):
        parse_genomic_hgvs("chr2:g.100_101ins")


@pytest.mark.parametrize(
    "text",
    [
        "chr2:g.5_3del",  # del: end 3 < start 5
        "chr2:g.5_3delinsAC",  # delins would collapse to a pure insertion (deletes nothing)
        "chr2:g.5_3dup",
        "chr2:g.6_5insA",  # insertion positions must be adjacent-ascending
        "chr2:g.2_0del",  # end 0 < start 2
    ],
)
def test_reversed_range_fails_closed(text: str) -> None:
    # A range whose end precedes its start is not a valid span. Un-guarded, it made
    # ref_lookup read a backwards empty slice, so the deleted/duplicated bases silently
    # vanished and a delins collapsed into an insertion — a phantom variant accepted with
    # no error. It must raise, like every other malformed-input case.
    with pytest.raises(ValueError, match="range end precedes start"):
        parse_genomic_hgvs(text)


def test_single_base_range_still_parses() -> None:
    # The guard allows end == start (a single-base range like `g.6_6del`); only a strictly
    # reversed span is rejected.
    p = parse_genomic_hgvs("chr2:g.6_6del")
    assert p.op is HgvsOp.DEL and p.start == 5 and p.end == 6


def test_adapter_substitution_to_variant() -> None:
    var = HgvsAdapter().to_variant("chr2:g.60100A>T", chrom="chr2")
    assert var.chrom == "chr2" and var.pos == 60099
    assert var.ref == "A" and var.alt == "T"
    assert var.hgvs_g == "chr2:g.60100A>T"


def test_adapter_deletion_fills_ref_from_lookup() -> None:
    # reference window [99, 102) is "CAT"; a stated-base del needs no lookup
    var = HgvsAdapter().to_variant(
        "chr2:g.100_102del", chrom="chr2", ref_lookup=lambda s, e: "CAT"[: e - s]
    )
    assert var.ref == "CAT" and var.alt == ""


def test_adapter_deletion_without_lookup_raises() -> None:
    with pytest.raises(ValueError, match="reference"):
        HgvsAdapter().to_variant("chr2:g.100_102del", chrom="chr2")


def test_adapter_coding_needs_projector() -> None:
    with pytest.raises(ValueError, match="projector"):
        HgvsAdapter().to_variant("NM_000518.5:c.20A>T", chrom="chr11")


def test_adapter_coding_uses_projector() -> None:
    adapter = HgvsAdapter(projector=lambda _c: "chr11:g.5226000A>T")
    var = adapter.to_variant("NM_000518.5:c.20A>T", chrom="chr11")
    assert var.pos == 5225999 and var.ref == "A" and var.alt == "T"


def test_parse_duplication() -> None:
    p = parse_genomic_hgvs("chr2:g.100_102dup")
    assert p.op is HgvsOp.DUP
    assert p.start == 99 and p.end == 102


def test_adapter_duplication_becomes_insertion() -> None:
    # dup of the 3-base span [99,102)='CAT' inserts 'CAT' just after it (pos 102)
    var = HgvsAdapter().to_variant(
        "chr2:g.100_102dup", chrom="chr2", ref_lookup=lambda s, e: "CAT"[: e - s]
    )
    assert var.pos == 102 and var.ref == "" and var.alt == "CAT"


def test_unsupported_expression_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        parse_genomic_hgvs("chr2:g.100inv")


def test_delins_without_bases_rejected() -> None:
    with pytest.raises(ValueError, match="replacement bases"):
        parse_genomic_hgvs("chr2:g.100_102delins")


def test_coding_hgvs_needs_projector() -> None:
    # Without a projector, a c./p. expression cannot be resolved.
    with pytest.raises(ValueError, match="projector"):
        HgvsAdapter().to_variant("NM_000518.5:c.20A>T", chrom="chr11")


def test_injected_projector_resolves_coding_to_genomic() -> None:
    # A fake projector stands in for the hgvs library: c. -> g., then native parse.
    adapter = HgvsAdapter(projector=lambda _c: "chr11:g.5226778A>T")
    var = adapter.to_variant("NM_000518.5:c.20A>T", chrom="chr11")
    assert var.chrom == "chr11" and var.pos == 5226777 and var.ref == "A" and var.alt == "T"


@pytest.mark.skipif(
    importlib.util.find_spec("hgvs") is not None,
    reason="hgvs installed; the import-guard path is not exercised",
)
def test_hgvs_library_projector_requires_hgvs() -> None:
    # With the optional library absent (the CI default), the backend setup raises
    # a clear, actionable error rather than an opaque ImportError.
    with pytest.raises(RuntimeError, match="hgvs"):
        HgvsLibraryProjector()("NM_000518.5:c.20A>T")
