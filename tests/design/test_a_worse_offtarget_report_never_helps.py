"""Adding an off-target must never make a candidate look better.

This is the class this project has shipped twice: a patient off-target masked on the
safety axis, and a benign ancestry-tagged site *raising* a candidate's safety score
because it switched `worst_ancestry()` onto a stratified path that never saw the danger.
Both were fixed by changing which sites reach the stratification. Neither fix left a
property test behind, so the invariant they restored is guarded only by the two specific
regressions.

One honest limit, found by mutating each clause of the attribution rule separately: of
the three conditions that credit a site to every ancestry (`REFERENCE`, `frequency is
None`, empty `ancestries`), two are independently pinned by this pool and the third —
`frequency is None` — is not, because every shape the engine emits with no frequency also
has an empty breakdown. Constructing a site with an ancestry breakdown and no frequency
would test a state the engine cannot produce, so the clause stays as defensive
redundancy and this test does not pretend to cover it.

Two statements, because they can fail independently: the safety axis itself must be
monotone under adding a site, and the composite ranking must not put a strictly worse
report ahead of an otherwise identical candidate. The first is swept over every subset of
a mixed pool — reference, population with an ancestry, patient, a second ancestry — since
the previous bugs both needed a *combination* of site origins to appear.
"""

from __future__ import annotations

import itertools

from alleleforge.design.ranking import _safety, rank_candidates
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.offtarget import (
    OffTargetReport,
    OffTargetSite,
    ScoreMethod,
    SiteOrigin,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

CLEAN_SPACER = "ACGTAACGTTACGTAACGTT"
DIRTY_SPACER = "ACGTAACGTTACGTAACGTA"


def _site(
    score: float,
    origin: SiteOrigin = SiteOrigin.REFERENCE,
    ancestry: str | None = None,
    start: int = 100,
) -> OffTargetSite:
    return OffTargetSite(
        locus=GenomicInterval(chrom="chr2", start=start, end=start + 20, strand=Strand.PLUS),
        mismatches=1,
        score=score,
        score_method=ScoreMethod.CFD,
        origin=origin,
        causal_allele="chr2:105:A>G" if origin is not SiteOrigin.REFERENCE else None,
        populations=(ancestry,) if ancestry else (),
        frequency=0.1 if ancestry else None,
        ancestries={ancestry: 0.1} if ancestry else {},
    )


def _guide(spacer: str) -> Guide:
    return Guide(
        spacer=Spacer(sequence=DNASequence(spacer)),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )


def _candidate(spacer: str, sites: tuple[OffTargetSite, ...]) -> DesignCandidate:
    return DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=_guide(spacer),
        offtarget=OffTargetReport(spacer=spacer, pam="NGG", sites=sites),
        rationale="fixture",
    )


#: A site whose presence is known but whose *attribution* is not: a population hit with a
#: frequency and an empty per-ancestry breakdown. It is in the pool because the three
#: clauses that make a site count toward every stratum overlap for the other shapes, so
#: without it two of them can be deleted with the property still holding.
_UNATTRIBUTED = OffTargetSite(
    locus=GenomicInterval(chrom="chr2", start=600, end=620, strand=Strand.PLUS),
    mismatches=1,
    score=0.70,
    score_method=ScoreMethod.CFD,
    origin=SiteOrigin.POPULATION,
    causal_allele="chr2:605:A>G",
    populations=("afr",),
    frequency=0.2,
    ancestries={},
)

_POOL = (
    _site(0.90, start=100),
    _site(0.20, SiteOrigin.POPULATION, "afr", 200),
    _site(0.05, start=300),
    _site(0.50, SiteOrigin.PATIENT, None, 400),
    _site(0.30, SiteOrigin.POPULATION, "eas", 500),
    _UNATTRIBUTED,
)


def test_adding_any_site_never_raises_safety() -> None:
    """Swept over every subset: both shipped bugs needed a combination of origins."""
    for size in range(len(_POOL) + 1):
        for combination in itertools.combinations(_POOL, size):
            before, _ = _safety(_candidate(CLEAN_SPACER, combination))
            for extra in _POOL:
                if extra in combination:
                    continue
                after, _ = _safety(_candidate(CLEAN_SPACER, (*combination, extra)))
                assert after <= before + 1e-12, (
                    f"adding a {extra.origin.value} site scoring {extra.score} raised "
                    f"safety {before:.3f} -> {after:.3f} on a report of {len(combination)}"
                )


def test_a_strictly_worse_report_does_not_rank_ahead() -> None:
    dirty = _candidate(DIRTY_SPACER, (_site(0.1), _site(0.95, start=500)))
    clean = _candidate(CLEAN_SPACER, (_site(0.1),))
    ranked = rank_candidates([dirty, clean]).candidates
    order = [str(c.guide.spacer.sequence) for c in ranked if c.guide is not None]
    assert order[0] == CLEAN_SPACER, "the candidate with an extra 0.95 off-target ranked first"


def test_an_unsearched_candidate_is_not_penalised_silently() -> None:
    """The deliberate asymmetry: no report scores 1.0, and the flag is what says so."""
    unsearched = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE, guide=_guide(CLEAN_SPACER), rationale="fixture"
    )
    assert _safety(unsearched) == (1.0, None)
    assert _safety(_candidate(CLEAN_SPACER, ()))[0] == 1.0
