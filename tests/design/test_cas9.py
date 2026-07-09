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


class _RecordingScorer:
    """A stub efficiency scorer that records the context window it is handed."""

    name = "recording"
    context_flank = (4, 3)  # request Rule Set 3's asymmetric 30-mer

    def __init__(self) -> None:
        self.seen: list[int] = []

    def score(self, context: str):  # type: ignore[no-untyped-def]
        from alleleforge.types.prediction import Prediction, UncertaintyMethod

        self.seen.append(len(context))
        return Prediction[float](value=0.5, interval=(0.4, 0.6), method=UncertaintyMethod.HEURISTIC)


def test_design_honors_scorer_context_flank(make_reference: MakeRef) -> None:
    # A scorer declaring context_flank=(4, 3) must be handed a 30-nt window.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    scorer = _RecordingScorer()
    rv = _resolve_at(ref, "chr2", 32)
    design_cas9(
        rv, EditIntent.CORRECT, reference=ref, efficiency_scorer=scorer, run_offtarget=False
    )
    assert scorer.seen and all(length == 30 for length in scorer.seen)


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


def test_offtarget_excludes_the_guides_own_on_target(make_reference: MakeRef) -> None:
    # The reference always contains each guide's own protospacer. Counting that
    # perfect self-match as an off-target would peg every guide's worst_score at
    # 1.0 (an inert safety axis) and cap specificity_score at 0.5. The design path
    # passes the guide's placement so its own locus is excluded, while a genuine
    # paralog at another locus stays. Here the sole match is the on-target, so a
    # clean guide reports zero off-targets and full specificity.
    ref = make_reference({"chr2": PAD + SPACER + "TGG" + PAD})
    cands = _design(ref, EditIntent.KNOCK_OUT)
    for c in cands:
        assert c.offtarget is not None
        own = (c.guide.placement.chrom, c.guide.placement.start, c.guide.placement.end)
        site_loci = {(s.locus.chrom, s.locus.start, s.locus.end) for s in c.offtarget.sites}
        assert own not in site_loci  # the guide's own on-target is never an off-target
    # The guide targeting the planted protospacer is clean once its self-match is
    # excluded — full specificity, live (non-zero) safety, which the pre-fix path
    # (self-match at 1.0) could never report.
    clean = [c for c in cands if c.offtarget is not None and c.offtarget.n_sites == 0]
    assert clean, "expected at least one guide with no off-targets after self-exclusion"
    assert clean[0].offtarget.specificity_score() == 1.0
    assert clean[0].offtarget.worst_score() == 0.0


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
