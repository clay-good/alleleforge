"""Tests for the variant resolver: dispatch, normalization, validation."""

from __future__ import annotations

import pytest

from alleleforge.data.clinvar import ClinVarDB
from alleleforge.data.dbsnp import DbSnpDB
from alleleforge.genome.coordinates import AmbiguousRegion, RegionFlagKind
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import ClinVarAccession, DbSnpId, Variant, VariantClass
from alleleforge.variant.effect import Consequence, Impact, StaticEffectPredictor, VariantEffect
from alleleforge.variant.resolver import RawTarget, VcfRecord, resolve


def _key(var: Variant) -> tuple[str, int, str, str]:
    return (var.chrom, var.pos, var.ref, var.alt)


# -- dispatch over input forms ------------------------------------------------


def test_resolve_coordinate_string(reference: ReferenceGenome) -> None:
    rv = resolve("chr2:6:A>G", reference=reference)
    assert _key(rv.variant) == ("chr2", 5, "A", "G")  # 1-based 6 -> 0-based
    assert rv.variant.variant_class is VariantClass.SNV
    assert rv.source == "coordinates"
    assert rv.variant.build == "hg38"


def test_resolve_vcf_record(reference: ReferenceGenome) -> None:
    rv = resolve(VcfRecord(chrom="chr2", pos=6, ref="A", alt="G"), reference=reference)
    assert _key(rv.variant) == ("chr2", 5, "A", "G")
    assert rv.source == "vcf"


def test_resolve_genomic_hgvs(reference: ReferenceGenome) -> None:
    rv = resolve("chr2:g.6A>G", reference=reference)
    assert _key(rv.variant) == ("chr2", 5, "A", "G")
    assert rv.source == "hgvs"
    assert rv.variant.hgvs_g == "chr2:g.6A>G"


def test_resolve_refseq_accession_maps_to_contig(reference: ReferenceGenome) -> None:
    rv = resolve("NC_000002.12:g.6A>T", reference=reference)
    assert rv.variant.chrom == "chr2" and rv.variant.pos == 5


def test_input_form_invariance(reference: ReferenceGenome) -> None:
    forms = [
        Variant(chrom="chr2", pos=5, ref="A", alt="G"),
        "chr2:6:A>G",
        VcfRecord(chrom="chr2", pos=6, ref="A", alt="G"),
        "chr2:g.6A>G",
    ]
    keys = {_key(resolve(f, reference=reference).variant) for f in forms}
    assert keys == {("chr2", 5, "A", "G")}


def test_resolution_is_idempotent(reference: ReferenceGenome) -> None:
    first = resolve("chr2:6:A>G", reference=reference).variant
    second = resolve(first, reference=reference).variant
    assert first == second


# -- ClinVar / dbSNP lookups --------------------------------------------------


def test_resolve_clinvar_accession_object(clinvar_db: ClinVarDB) -> None:
    rv = resolve(ClinVarAccession(value="VCV000000012"), clinvar=clinvar_db)
    assert _key(rv.variant) == ("chr2", 60099, "A", "T")
    assert rv.source == "clinvar"


def test_resolve_clinvar_accession_string(clinvar_db: ClinVarDB) -> None:
    rv = resolve("VCV000000012", clinvar=clinvar_db)
    assert rv.variant.clinvar is not None


def test_resolve_rsid(dbsnp_db: DbSnpDB) -> None:
    rv = resolve(DbSnpId(value="rs114518452"), dbsnp=dbsnp_db)
    assert _key(rv.variant) == ("chr2", 60200, "G", "A")
    assert rv.source == "rsid"


def test_resolve_rsid_string(dbsnp_db: DbSnpDB) -> None:
    assert resolve("rs334", dbsnp=dbsnp_db).variant.pos == 60099


def test_clinvar_without_db_raises() -> None:
    with pytest.raises(ValueError, match="clinvar="):
        resolve(ClinVarAccession(value="VCV000000012"))


def test_rsid_without_db_raises() -> None:
    with pytest.raises(ValueError, match="dbsnp="):
        resolve("rs334")


# -- normalization, left-alignment, validation --------------------------------


@pytest.mark.parametrize("one_based_pos", [15, 16, 17])
def test_deletion_left_aligns_to_repeat_start(
    reference: ReferenceGenome, one_based_pos: int
) -> None:
    # Deleting any A from the chr2 homopolymer (0-based 14-16) must left-align
    # to the same canonical anchored deletion at the run's left edge.
    rv = resolve(f"chr2:{one_based_pos}:A>", reference=reference)
    assert _key(rv.variant) == ("chr2", 13, "CA", "C")


def test_hgvs_deletion_left_aligns(reference: ReferenceGenome) -> None:
    rv = resolve("chr2:g.15del", reference=reference)
    assert _key(rv.variant) == ("chr2", 13, "CA", "C")


def test_insertion_is_anchored(reference: ReferenceGenome) -> None:
    rv = resolve("chr2:g.6_7insGG", reference=reference)
    assert _key(rv.variant) == ("chr2", 5, "A", "AGG")


def test_suffix_anchored_deletion_left_aligns(reference: ReferenceGenome) -> None:
    # A right-anchored deletion (ref='AG', alt='G' at the run's 3' edge) that
    # bcftools-norm's prefix trimming alone would not fix still left-aligns.
    rv = resolve(Variant(chrom="chr2", pos=16, ref="AG", alt="G"), reference=reference)
    assert _key(rv.variant) == ("chr2", 13, "CA", "C")


def test_coding_hgvs_via_projector(reference: ReferenceGenome) -> None:
    from alleleforge.variant.hgvs_adapter import HgvsAdapter

    adapter = HgvsAdapter(projector=lambda _c: "chr2:g.6A>T")
    rv = resolve("NM_000518.5:c.20A>T", reference=reference, hgvs=adapter)
    assert _key(rv.variant) == ("chr2", 5, "A", "T")
    assert rv.source == "hgvs"


def test_reference_mismatch_is_hard_error(reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError, match="reference mismatch"):
        resolve("chr2:6:T>G", reference=reference)


def test_resolution_without_reference_skips_validation() -> None:
    # No reference supplied: a wrong-looking ref is not validated, just normalized.
    rv = resolve("chr2:6:T>G")
    assert _key(rv.variant) == ("chr2", 5, "T", "G")


# -- working interval, effect, recommendation ---------------------------------


def test_working_interval_clamped_to_contig(reference: ReferenceGenome) -> None:
    rv = resolve("chr2:6:A>G", reference=reference, window=100)
    assert rv.working_interval.start == 0
    assert rv.working_interval.end == len("TTTTTACGTACGTCAAAGTTGGCCAATTGG")


def test_effect_annotation(reference: ReferenceGenome) -> None:
    var = Variant(chrom="chr2", pos=5, ref="A", alt="G", build="hg38")
    predictor = StaticEffectPredictor()
    predictor.add(var, VariantEffect(consequence=Consequence.MISSENSE, impact=Impact.MODERATE))
    rv = resolve("chr2:6:A>G", reference=reference, effect=predictor)
    assert rv.effect is not None and rv.effect.consequence is Consequence.MISSENSE


def test_reference_recommendation_wired(reference: ReferenceGenome) -> None:
    region = AmbiguousRegion(
        interval=GenomicInterval(chrom="chr2", start=0, end=30, strand=Strand.PLUS),
        kind=RegionFlagKind.SEGDUP,
    )
    rv = resolve("chr2:6:A>G", reference=reference, ambiguous_regions=(region,))
    assert rv.reference_recommendation is not None
    assert rv.reference_recommendation.recommended


def test_no_recommendation_when_clear(reference: ReferenceGenome) -> None:
    rv = resolve("chr2:6:A>G", reference=reference)
    assert rv.reference_recommendation is None


# -- raw target sequence ------------------------------------------------------


def test_raw_target_resolves_on_synthetic_contig() -> None:
    target = RawTarget(sequence=DNASequence("ACGTAACGT"), position=4, ref="A", alt="G")
    rv = resolve(target)
    assert rv.variant.chrom == "target"
    assert _key(rv.variant) == ("target", 4, "A", "G")
    assert rv.source == "raw_sequence"


def test_raw_target_validates_ref_against_sequence() -> None:
    with pytest.raises(ValueError, match="!= sequence"):
        RawTarget(sequence=DNASequence("ACGT"), position=0, ref="G", alt="T")


# -- malformed input ----------------------------------------------------------


def test_unrecognized_input_raises() -> None:
    with pytest.raises(ValueError, match="unrecognized variant input"):
        resolve("not a variant")


def test_bare_hgvs_without_contig_raises(reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError, match="contig prefix"):
        resolve("g.6A>T", reference=reference)


def test_unmapped_refseq_raises(reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError, match="cannot map"):
        resolve("NC_000099.1:g.6A>T", reference=reference)
