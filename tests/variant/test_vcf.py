"""Tests for the cyvcf2 fast path (R4): stream a VCF into the cohort designer.

cyvcf2 is an optional, htslib-backed dependency absent from the CI install, so the
splitting/filtering logic is covered with a fake reader duck-typed to the cyvcf2
``Variant`` shape and an injectable opener — no native library required.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.variant import VcfVariantLike, iter_vcf
from alleleforge.variant.resolver import VcfRecord


@dataclass
class FakeVariant:
    """A minimal stand-in for a ``cyvcf2.Variant`` (1-based POS, FILTER None=PASS)."""

    CHROM: str
    POS: int
    REF: str
    ALT: list[str]
    ID: str | None = None
    FILTER: str | None = None


@dataclass
class FakeVcf:
    """An iterable of records, like ``cyvcf2.VCF(path)``."""

    records: list[FakeVariant] = field(default_factory=list)

    def __iter__(self) -> Iterator[FakeVariant]:
        return iter(self.records)


def test_fake_variant_satisfies_protocol() -> None:
    v = FakeVariant("chr1", 100, "A", ["G"])
    assert isinstance(v, VcfVariantLike)


def test_yields_one_record_per_concrete_alt() -> None:
    records = [FakeVariant("chr2", 26, "A", ["G", "T"], ID="rs1")]
    out = list(iter_vcf(records))
    assert out == [
        VcfRecord(chrom="chr2", pos=26, ref="A", alt="G", rsid="rs1"),
        VcfRecord(chrom="chr2", pos=26, ref="A", alt="T", rsid="rs1"),
    ]


def test_skips_symbolic_and_spanning_alleles() -> None:
    records = [
        FakeVariant("chr1", 10, "A", ["<DEL>", "*", "G"]),
        FakeVariant("chr1", 20, "N", ["A"]),  # N ref is concrete (ACGTN)
        FakeVariant("chr1", 30, "<INS>", ["A"]),  # symbolic ref -> whole row skipped
    ]
    out = list(iter_vcf(records))
    assert out == [
        VcfRecord(chrom="chr1", pos=10, ref="A", alt="G"),
        VcfRecord(chrom="chr1", pos=20, ref="N", alt="A"),
    ]


def test_pass_only_filters_soft_filtered_calls() -> None:
    records = [
        FakeVariant("chr1", 10, "A", ["G"], FILTER=None),  # PASS
        FakeVariant("chr1", 20, "A", ["G"], FILTER="LowQual"),  # soft-filtered
    ]
    assert [r.pos for r in iter_vcf(records)] == [10]
    assert [r.pos for r in iter_vcf(records, pass_only=False)] == [10, 20]


def test_drops_placeholder_rsid() -> None:
    (only,) = list(iter_vcf([FakeVariant("chr1", 10, "A", ["G"], ID=".")]))
    assert only.rsid is None


def test_path_uses_injected_opener() -> None:
    opened: list[str] = []

    def opener(path: str) -> FakeVcf:
        opened.append(path)
        return FakeVcf([FakeVariant("chr1", 5, "C", ["T"])])

    out = list(iter_vcf(Path("/tmp/cohort.vcf.gz"), opener=opener))
    assert opened == ["/tmp/cohort.vcf.gz"]
    assert out == [VcfRecord(chrom="chr1", pos=5, ref="C", alt="T")]


def test_path_without_cyvcf2_raises_clear_error() -> None:
    # No opener + cyvcf2 absent from the CI env -> a clear, actionable RuntimeError.
    try:
        import cyvcf2  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="cyvcf2"):
            list(iter_vcf("/nonexistent.vcf"))
    else:  # pragma: no cover - only when cyvcf2 happens to be installed
        pytest.skip("cyvcf2 is installed; the import-guard branch is unreachable")


# --- end-to-end: the stream feeds design_many lazily -------------------------

PAD = "T" * 20
ABE_PROTO = "TTTAAACGTTTTTTTTTTTT"  # in-window A at chr2:26 (1-based), NGG PAM downstream
CONTIG = PAD + ABE_PROTO + "TGG" + PAD


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "vcf_cohort.fa"
    fasta.write_text(f">chr2\n{CONTIG}\n")
    return ReferenceGenome(fasta, build="hg38")


def test_stream_drives_design_many(reference: ReferenceGenome) -> None:
    records = [
        FakeVariant("chr2", 26, "A", ["G"], ID="rs9"),  # designable A>G
        FakeVariant("chr2", 26, "C", ["G"], FILTER="LowQual"),  # filtered out, wrong ref anyway
    ]
    report = design_many(iter_vcf(records), reference=reference, intent=EditIntent.INSTALL)
    assert (report.total, report.succeeded, report.failed) == (1, 1, 0)
    (item,) = report.items
    assert item.summary is not None and item.summary["best_chemistry"] == "base_abe"


def test_an_allele_using_every_permitted_base_is_still_concrete() -> None:
    """`set(a) <= set("ACGTN")` — subset *or equal*, not proper subset.

    Tightened to `<`, an allele that happens to use all five permitted characters is
    rejected as symbolic and the record is skipped with the `<DEL>`/breakend family. That
    is reachable by ordinary data: any indel allele long enough to contain an ambiguous
    base alongside all four bases, such as `ACGTN` or `NACGTACGT`. The record does not
    error — it is counted as symbolic and dropped, so a designable variant disappears from
    a cohort with a reason that does not apply to it.
    """
    from alleleforge.variant.vcf import _is_concrete

    assert _is_concrete("ACGTN") is True, "all five permitted characters is not symbolic"
    assert _is_concrete("NACGTACGT") is True
    # A proper subset is concrete too, so the check above is not the only passing case.
    assert _is_concrete("ACGT") is True
    assert _is_concrete("N") is True


def test_a_symbolic_or_out_of_alphabet_allele_is_not_concrete() -> None:
    """The other side, so the subset rule is measured rather than assumed."""
    from alleleforge.variant.vcf import _is_concrete

    assert _is_concrete("<DEL>") is False
    assert _is_concrete("*") is False
    assert _is_concrete("ACGTX") is False, "a character outside the alphabet is not designable"
