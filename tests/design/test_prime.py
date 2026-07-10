"""End-to-end tests for the prime-editing design vertical (the flagship)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alleleforge.data.annotations import EncodeTracks, _Segment
from alleleforge.design.prime import design_prime
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


def _context() -> str:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # plus pegRNA PAM
    # minus ngRNA PAM: proto_lo = 58 + 3 = 61, so the PAM-proximal seed [61, 71)
    # spans the edit at 70 -> a genuine PE3b (measured from the minus-strand
    # PAM-proximal end, not proto_hi).
    seq[58:61] = list("CCA")
    return "".join(seq)


def _design(make_reference: MakeRef, **kw: object) -> list[DesignCandidate]:
    ref = make_reference({"chr2": _context()})
    base = str(ref.fetch(GenomicInterval(chrom="chr2", start=70, end=71, strand=Strand.PLUS)))
    rv: ResolvedVariant = resolve(f"chr2:71:{base}>C", reference=ref)
    return design_prime(rv, EditIntent.INSTALL, reference=ref, max_candidates=50, **kw)


def test_unifies_all_four_axes(make_reference: MakeRef) -> None:
    # The flagship requirement: variant input, ML efficiency with OOD honesty,
    # outcome/byproduct prediction, and population-aware off-target — all present.
    candidates = _design(make_reference)
    assert candidates
    top = candidates[0]
    assert top.chemistry is Chemistry.PRIME
    assert top.pegrna is not None  # variant -> pegRNA
    assert top.efficiency is not None and top.efficiency.interval_level == 0.80
    assert top.outcome is not None and top.outcome.p_intended >= 0.0
    assert isinstance(top.offtarget, OffTargetReport)


def test_off_target_searches_both_nicks(make_reference: MakeRef) -> None:
    top = _design(make_reference)[0]
    assert top.pegrna is not None and top.pegrna.nicking_guide is not None
    assert "both-nicks-searched" in top.flags
    assert isinstance(top.offtarget.ancestry_stratification(), dict)


def test_pe3_merged_report_keeps_scorer_and_matrix(make_reference: MakeRef) -> None:
    # A PE3/PE3b candidate's two-nick off-target reports are merged into one. The
    # merge must carry the scorer/matrix identity forward — otherwise the report
    # renders no "scoring basis" line for the flagship chemistry (a published-CFD
    # table would look identical to an approximation-scored one), and the
    # sub-threshold tail must survive so specificity is not silently overstated.
    top = _design(make_reference)[0]
    assert top.pegrna is not None and top.pegrna.nicking_guide is not None  # PE3/PE3b
    report = top.offtarget
    assert report is not None
    assert report.scorer == "CFD"
    assert report.score_matrix == "doench-2016-cfd"
    assert report.subthreshold_score_sum >= 0.0


def test_epegrna_and_pe3b_flagged(make_reference: MakeRef) -> None:
    top = _design(make_reference)[0]
    assert any(f.startswith("epegRNA:") for f in top.flags)
    assert "pe3b" in top.flags  # the seed-disrupting ngRNA is selected


def test_ranked_by_efficiency(make_reference: MakeRef) -> None:
    effs = [c.efficiency.value for c in _design(make_reference) if c.efficiency]
    assert effs == sorted(effs, reverse=True)


def test_ood_honesty_surfaced(make_reference: MakeRef) -> None:
    candidates = _design(make_reference, cell_context="primary_T_cell", run_offtarget=False)
    top = candidates[0]
    assert top.efficiency is not None and top.efficiency.in_distribution is False
    assert "ood" in top.flags


def test_run_offtarget_false(make_reference: MakeRef) -> None:
    for c in _design(make_reference, run_offtarget=False):
        assert c.offtarget is None


def _atac(value: float) -> EncodeTracks:
    # An accessibility track covering the whole synthetic chr2, so every pegRNA
    # placement gets the same signal.
    return EncodeTracks({("atac", "chr2"): [_Segment(start=0, end=300, value=value)]})


def _eff_by_pegrna(cands: list[DesignCandidate]) -> dict[str, float]:
    # pegRNAs share a spacer but differ in PBS/RTT geometry, so key on the full
    # pegRNA identity, not the spacer, to compare like with like.
    return {
        c.pegrna.model_dump_json(): c.efficiency.value for c in cands if c.pegrna and c.efficiency
    }


def test_chromatin_opt_in_leaves_baseline_unchanged(make_reference: MakeRef) -> None:
    # With no tracks, efficiency is the pure geometry baseline — wiring chromatin
    # must not perturb the default path.
    base = _eff_by_pegrna(_design(make_reference, run_offtarget=False))
    # Passing tracks but no track name is also a no-op (adjustment needs both).
    none_track = _eff_by_pegrna(
        _design(make_reference, encode_tracks=_atac(2.0), run_offtarget=False)
    )
    assert base == none_track
    assert all("chromatin-adjusted" not in c.rationale for c in _design(make_reference))


def test_open_chromatin_raises_efficiency_and_labels_it(make_reference: MakeRef) -> None:
    base = _eff_by_pegrna(_design(make_reference, run_offtarget=False))
    adjusted = _design(
        make_reference, encode_tracks=_atac(2.0), chromatin_track="atac", run_offtarget=False
    )
    moved = 0
    for c in adjusted:
        assert c.pegrna is not None and c.efficiency is not None
        if c.efficiency.value > base[c.pegrna.model_dump_json()]:
            moved += 1
            assert "chromatin-adjusted" in c.rationale  # the boost is disclosed
    assert moved  # open chromatin raised at least one candidate's efficiency


def test_chromatin_does_not_launder_an_ood_prediction(make_reference: MakeRef) -> None:
    # A chromatin boost must never flip the OOD flag to in-distribution.
    top = _design(
        make_reference,
        cell_context="primary_T_cell",
        encode_tracks=_atac(2.0),
        chromatin_track="atac",
        run_offtarget=False,
    )[0]
    assert top.efficiency is not None and top.efficiency.in_distribution is False
    assert "ood" in top.flags


def test_uncovered_locus_is_a_no_op(make_reference: MakeRef) -> None:
    # A track with no coverage over the pegRNA loci (signal 0) leaves efficiency at
    # the baseline — no penalty for missing data, and no false "adjusted" label.
    base = _eff_by_pegrna(_design(make_reference, run_offtarget=False))
    empty = EncodeTracks({("atac", "chr2"): [_Segment(start=5000, end=5100, value=9.0)]})
    for c in _design(
        make_reference, encode_tracks=empty, chromatin_track="atac", run_offtarget=False
    ):
        assert c.pegrna is not None and c.efficiency is not None
        assert c.efficiency.value == base[c.pegrna.model_dump_json()]
        assert "chromatin-adjusted" not in c.rationale


def test_unknown_chromatin_track_fails_closed(make_reference: MakeRef) -> None:
    # A mis-named track must raise, not silently return an unadjusted efficiency
    # that the caller believes is chromatin-aware.
    with pytest.raises(KeyError):
        _design(
            make_reference,
            encode_tracks=_atac(2.0),
            chromatin_track="missing",
            run_offtarget=False,
        )


def test_non_editable_variant_empty(make_reference: MakeRef) -> None:
    ref = make_reference({"chr2": _context()})
    rv = resolve("chr2:71:ATA>A", reference=ref)  # not a single-position edit
    assert design_prime(rv, EditIntent.CORRECT, reference=ref) == []


def test_pol3_gc_and_5prime_g_annotated(make_reference: MakeRef) -> None:
    # The AT-heavy synthetic context yields a low-GC protospacer that does not
    # start with G, so both Pol-III caveats are surfaced as inspectable flags
    # (annotations, not a silent drop).
    top = _design(make_reference)[0]
    assert any(f.startswith("gc-out-of-band:") for f in top.flags)
    assert top.pegrna is not None
    spacer = str(top.pegrna.spacer.sequence).upper()
    assert ("no-5prime-g" in top.flags) == (not spacer.startswith("G"))
