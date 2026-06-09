"""Fixtures for the Phase 11 reporting tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.edit import EditIntent
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
PAD = "T" * 20


@pytest.fixture
def make_reference(tmp_path: Path) -> MakeRef:
    """Return a factory building a :class:`ReferenceGenome` from inline contigs."""
    counter = {"n": 0}

    def _make(contigs: dict[str, str]) -> ReferenceGenome:
        counter["n"] += 1
        fasta = tmp_path / f"ref{counter['n']}.fa"
        fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
        return ReferenceGenome(fasta, build="hg38")

    return _make


def _resolve(ref: ReferenceGenome, zero_based: int, alt: str) -> object:
    base = str(
        ref.fetch(
            GenomicInterval(chrom="chr2", start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"chr2:{zero_based + 1}:{base}>{alt}", reference=ref)


@pytest.fixture
def abe_menu(make_reference: MakeRef) -> RankedMenu:
    """A ranked menu with base-editor (sgRNA) candidates for an A->G install."""
    ref = make_reference({"chr2": PAD + "TTTAAACGTTTTTTTTTTTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    return design(rv, reference=ref, intent=EditIntent.INSTALL)


@pytest.fixture
def prime_menu(make_reference: MakeRef) -> RankedMenu:
    """A ranked menu with prime (pegRNA) candidates for an A->C install."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # plus pegRNA PAM
    seq[55:58] = list("CCA")  # minus ngRNA PAM (PE3b)
    ref = make_reference({"chr2": "".join(seq)})
    rv = _resolve(ref, 70, "C")
    return design(rv, reference=ref, intent=EditIntent.INSTALL, max_candidates_per_chemistry=5)


@pytest.fixture
def nuclease_menu(make_reference: MakeRef) -> RankedMenu:
    """A ranked menu with SpCas9 nuclease (sgRNA) candidates for a knock-out."""
    ref = make_reference({"chr2": PAD + "ACGTAACGTTACGTAACGTT" + "TGG" + PAD})
    rv = _resolve(ref, 25, "G")
    return design(rv, reference=ref, intent=EditIntent.KNOCK_OUT)


@pytest.fixture
def ancestry_menu() -> RankedMenu:
    """A synthetic menu whose top candidate has ancestry-annotated off-targets.

    Built directly (no gnomAD wiring) so the ancestry-stratified rendering path
    is exercised deterministically: one reference site and one African-enriched
    population site.
    """
    from alleleforge.types.candidate import DesignCandidate, RankedMenu
    from alleleforge.types.edit import AlleleOutcome, Chemistry, EditOutcome
    from alleleforge.types.guide import PAM, Guide, Spacer
    from alleleforge.types.offtarget import (
        OffTargetReport,
        OffTargetSite,
        ScoreMethod,
        SiteOrigin,
    )
    from alleleforge.types.prediction import Prediction, UncertaintyMethod
    from alleleforge.types.provenance import ModelCheckpoint, Provenance
    from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

    spacer = "ACGTAACGTTACGTAACGTT"
    guide = Guide(
        spacer=Spacer(sequence=DNASequence(spacer)),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr11", start=100, end=120, strand=Strand.PLUS),
        cut_site=117,
    )
    report = OffTargetReport(
        spacer=spacer,
        pam="NGG",
        sites=(
            OffTargetSite(
                locus=GenomicInterval(chrom="chr3", start=10, end=30, strand=Strand.PLUS),
                mismatches=3,
                score=0.18,
                score_method=ScoreMethod.CFD,
            ),
            OffTargetSite(
                locus=GenomicInterval(chrom="chr3", start=500, end=520, strand=Strand.PLUS),
                mismatches=1,
                score=0.74,
                score_method=ScoreMethod.CFD,
                origin=SiteOrigin.POPULATION,
                causal_allele="chr3:510:A>G",
                populations=("afr",),
                frequency=0.06,
                ancestries={"afr": 0.06, "eur": 0.0},
            ),
        ),
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        efficiency=Prediction[float](
            value=0.62, interval=(0.5, 0.74), method=UncertaintyMethod.ENSEMBLE
        ),
        outcome=EditOutcome(
            alleles=(
                AlleleOutcome(allele="+1", probability=0.6, is_intended=True),
                AlleleOutcome(allele="-2", probability=0.4),
            )
        ),
        offtarget=report,
        flags=("population-offtarget",),
        rationale="synthetic ancestry fixture",
    )
    return RankedMenu(
        candidates=(candidate,),
        pareto_front=(0,),
        rationale="synthetic",
        provenance=Provenance.capture(
            alleleforge_version="0.0.0",
            seed=1,
            models=(
                ModelCheckpoint(
                    name="cas9-efficiency-ensemble",
                    version="0.1",
                    chemistry="cas9_nuclease",
                    license="MIT",
                ),
                ModelCheckpoint(
                    name="indelphi", version="1.0", chemistry="cas9_nuclease", license="MIT"
                ),
            ),
        ),
    )
