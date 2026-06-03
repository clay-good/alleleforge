"""End-to-end tests for the SpCas9 design vertical."""

from __future__ import annotations

from collections.abc import Callable

from alleleforge.design.cas9 import design_cas9
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.scoring.cas9_efficiency import RuleSet3Scorer
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _resolve_at(ref: ReferenceGenome, contig: str, zero_based: int) -> ResolvedVariant:
    base = str(
        ref.fetch(
            GenomicInterval(chrom=contig, start=zero_based, end=zero_based + 1, strand=Strand.PLUS)
        )
    )
    return resolve(f"{contig}:{zero_based + 1}:{base}>G", reference=ref)


def _design(ref: ReferenceGenome, intent: EditIntent, **kw: object) -> list[DesignCandidate]:
    rv = _resolve_at(ref, "chr2", 32)
    return design_cas9(rv, intent, reference=ref, efficiency_scorer=RuleSet3Scorer(), **kw)


def test_end_to_end_yields_candidates(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    candidates = _design(ref, EditIntent.KNOCK_OUT)
    assert candidates
    top = candidates[0]
    assert top.chemistry is Chemistry.CAS9_NUCLEASE
    assert top.guide is not None


def test_every_candidate_has_all_axes(make_reference: MakeRef) -> None:
    # The Phase 10 completeness property, checked on the cas9 path: efficiency,
    # outcome, and off-target are all populated.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    for c in _design(ref, EditIntent.KNOCK_OUT):
        assert c.efficiency is not None
        assert c.efficiency.interval[0] <= c.efficiency.value <= c.efficiency.interval[1]
        assert c.efficiency.interval_level == 0.80
        assert c.outcome is not None and c.outcome.alleles
        assert isinstance(c.offtarget, OffTargetReport)


def test_candidates_sorted_by_efficiency(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + ("A" * 40) + SPACER + "TGG" + PAD})
    effs = [c.efficiency.value for c in _design(ref, EditIntent.KNOCK_OUT) if c.efficiency]
    assert effs == sorted(effs, reverse=True)


def test_knockout_marks_frameshifts_intended(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    ko = _design(ref, EditIntent.KNOCK_OUT)[0]
    correct = _design(ref, EditIntent.CORRECT)[0]
    assert ko.outcome is not None and ko.outcome.p_intended > 0.0
    assert correct.outcome is not None and correct.outcome.p_intended == 0.0


def test_offtarget_is_ancestry_stratifiable(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    cand = _design(ref, EditIntent.KNOCK_OUT)[0]
    assert cand.offtarget is not None
    # the report exposes ancestry stratification by construction
    assert isinstance(cand.offtarget.ancestry_stratification(), dict)


def test_run_offtarget_false_skips(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    for c in _design(ref, EditIntent.KNOCK_OUT, run_offtarget=False):
        assert c.offtarget is None


def test_max_candidates_caps(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + ("A" * 40) + SPACER + "TGG" + PAD})
    assert len(_design(ref, EditIntent.KNOCK_OUT, max_candidates=1)) == 1


def test_rationale_recorded(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    top = _design(ref, EditIntent.KNOCK_OUT)[0]
    assert top.rationale is not None and "efficiency" in top.rationale
