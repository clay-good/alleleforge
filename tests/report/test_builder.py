"""Tests for the Phase 11 report builder."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alleleforge.report.builder import (
    RESEARCH_USE_DISCLAIMER,
    DesignReport,
    _reagent_summary,
    build_report,
)
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import PegRNA, Spacer
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.sequence import DNASequence


def test_build_report_basic(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu, variant="chr2:70:A>C", intent="install")
    assert isinstance(report, DesignReport)
    assert report.disclaimer == RESEARCH_USE_DISCLAIMER
    assert report.variant == "chr2:70:A>C"
    assert report.intent == "install"
    assert len(report.candidates) == len(prime_menu.candidates)


def test_report_carries_provenance(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    assert report.provenance is not None
    assert report.provenance.alleleforge_version


def test_intent_falls_back_to_provenance(prime_menu: RankedMenu) -> None:
    # design() stamps intent into provenance; build_report reads it if not given.
    report = build_report(prime_menu)
    assert report.intent == "install"


def test_ranks_are_one_based_and_ordered(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    assert [c.rank for c in report.candidates] == list(range(1, len(report.candidates) + 1))


def test_pareto_flag_matches_menu(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    flagged = {c.rank - 1 for c in report.candidates if c.on_pareto_front}
    assert flagged == set(prime_menu.pareto_front)


def test_every_candidate_axes_populated(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    for c in report.candidates:
        assert c.efficiency is not None
        assert c.outcome_top  # at least one outcome allele
        assert c.n_offtarget_sites is not None
        assert c.reagent and c.reagent != "no reagent"


def test_candidate_carries_aggregate_specificity(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    for c in report.candidates:
        assert c.offtarget_specificity is not None
        assert 0.0 < c.offtarget_specificity <= 1.0


def test_offtarget_table_is_ancestry_stratified(abe_menu: RankedMenu) -> None:
    report = build_report(abe_menu)
    top = report.candidates[0]
    # ancestry rows are sorted worst-first when present
    scores = [r.worst_score for r in top.offtarget_by_ancestry]
    assert scores == sorted(scores, reverse=True)


def test_oligos_attached_by_default(nuclease_menu: RankedMenu) -> None:
    report = build_report(nuclease_menu)
    assert report.candidates[0].oligos is not None


def test_oligos_can_be_omitted(nuclease_menu: RankedMenu) -> None:
    report = build_report(nuclease_menu, with_oligos=False)
    assert all(c.oligos is None for c in report.candidates)


def test_top_alleles_caps_outcomes(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu, top_alleles=2)
    assert all(len(c.outcome_top) <= 2 for c in report.candidates)


def test_report_json_roundtrips(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu)
    restored = DesignReport.model_validate_json(report.model_dump_json())
    assert restored == report


def test_ancestry_stratification_populated(ancestry_menu: RankedMenu) -> None:
    report = build_report(ancestry_menu)
    top = report.candidates[0]
    by = {r.ancestry: r.worst_score for r in top.offtarget_by_ancestry}
    # the reference site (score 0.18) contributes to every ancestry; the
    # population site (0.74) only to afr — so afr is the worst-affected.
    assert by["afr"] == 0.74
    assert by["eur"] == 0.18
    assert [r.worst_score for r in top.offtarget_by_ancestry] == sorted(
        (r.worst_score for r in top.offtarget_by_ancestry), reverse=True
    )


def test_candidate_carries_offtarget_scoring_basis(ancestry_menu: RankedMenu) -> None:
    # The scorer identity and matrix are surfaced onto the report so the render can
    # name the scoring basis (published CFD vs. the labeled approximation).
    top = build_report(ancestry_menu).candidates[0]
    assert top.offtarget_scorer == "CFD"
    assert top.offtarget_matrix == "doench-2016-cfd"


def test_pegrna_reagent_line_says_what_the_rt_template_writes() -> None:
    """A ΔF508-style correction and an SNV must not read identically.

    The reagent line is the one string a bench reader scans. Two pegRNAs can share
    a spacer length, a PBS, an RTT length, a motif and a nick type while installing
    completely different edits — one substituting a base, one restoring four.
    """
    peg = PegRNA(
        spacer=Spacer(sequence=DNASequence("ACGTACGTACGTACGTACGT")),
        scaffold=DNASequence("GTTTTAGAGCTAGAAATAGCAAG"),
        rtt=DNASequence("A" * 16),
        pbs=DNASequence("ACGTACGTACGTA"),
        rtt_homology_5prime=7,
        rtt_homology_3prime=5,
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.PRIME,
        pegrna=peg,
        efficiency=Prediction[float](
            value=0.5,
            interval=(0.4, 0.6),
            interval_level=0.8,
            method=UncertaintyMethod.HEURISTIC,
        ),
    )
    assert "writing 4 nt" in _reagent_summary(candidate)


def test_a_precise_nuclease_reagent_line_names_its_donor() -> None:
    """Naming only the guide would describe half a reagent."""
    from alleleforge.types.guide import PAM, Guide, HDRDonor
    from alleleforge.types.sequence import GenomicInterval, Strand

    guide = Guide(
        spacer=Spacer(sequence=DNASequence("ACGTACGTACGTACGTACGT")),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )
    donor = HDRDonor(sequence=DNASequence("ACGT" * 25), recut_blocked=True, note="n")
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        hdr_donor=donor,
        efficiency=Prediction[float](
            value=0.5, interval=(0.4, 0.6), interval_level=0.8, method=UncertaintyMethod.HEURISTIC
        ),
    )
    summary = _reagent_summary(candidate)
    assert "HDR donor 100 nt" in summary
    assert "re-cut blocked" in summary
    # A knock-out candidate has no donor and must not grow the clause.
    assert "HDR donor" not in _reagent_summary(candidate.model_copy(update={"hdr_donor": None}))


def test_the_report_carries_the_menu_rationale(prime_menu: RankedMenu) -> None:
    """An empty report with no explanation is the worst artifact a render can produce.

    The designer degrades gracefully when a chemistry fails and records exactly what
    happened in the menu's rationale — which chemistries routed, which ran, which
    were skipped and why. `DesignReport` had no field for it, so every renderer
    dropped it: a mistyped option produced zero candidates, exit 0, and no
    explanation anywhere in the JSON, TSV, HTML or PDF.
    """
    report = build_report(prime_menu)
    assert report.rationale == prime_menu.rationale
    assert report.rationale


def test_the_provenance_footer_accounts_for_every_provenance_field() -> None:
    """Adding a field to `Provenance` must force a render-or-omit decision.

    The footer had grown `models` and stopped, so a report named the code that ran
    but not the data it ran on — and "population-aware" is a claim about the data,
    not the code. Enumerating fields by hand is how that happens; this test makes the
    hand-enumeration checkable, so the next field cannot be forgotten silently.
    """
    from alleleforge.report.builder import PROVENANCE_FOOTER_OMITTED, provenance_lines
    from alleleforge.types.provenance import (
        DatasetVersion,
        ModelCheckpoint,
        Provenance,
        ToolVersion,
    )

    full = Provenance(
        alleleforge_version="9.9.9",
        reference_build="hg38",
        seed=7,
        tools=(ToolVersion(name="bowtie2", version="2.5.4"),),
        datasets=(DatasetVersion(name="gnomad", version="v4.1"),),
        models=(ModelCheckpoint(name="deepcas9", version="1.2"),),
        config_snapshot={"intent": "correct"},
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    rendered = " · ".join(provenance_lines(full))

    for field in Provenance.model_fields:
        if field in PROVENANCE_FOOTER_OMITTED:
            continue
        value = getattr(full, field)
        # A tuple of records renders by name; a scalar renders as itself.
        if isinstance(value, tuple):
            needle = str(value[0].name)  # a tuple of records renders by name
        elif isinstance(value, datetime):
            needle = value.isoformat()
        else:
            needle = str(value)
        assert needle in rendered, f"{field} is neither rendered nor listed as omitted"

    # ...and every declared omission is a real field, so the list cannot rot into an
    # excuse for a field that no longer exists.
    assert set(PROVENANCE_FOOTER_OMITTED) <= set(Provenance.model_fields)


def test_model_limitations_reach_a_render(ancestry_menu: RankedMenu) -> None:
    """A card's limits were carried "for safety audit" and shown to nobody.

    `ModelCheckpoint.known_failure_modes` exists so a result is self-contained
    "without re-opening the cards" — and no render printed it, so the audit still
    meant re-opening the cards. Worse, `to_checkpoint()` dropped `out_of_scope_use`
    on the way in, so the provenance carried how a model fails but not what it was
    never meant to do. The shipped `cas9-efficiency-ensemble` card says its point
    estimate is "an unfitted pseudo-random scaffold"; every report was silent on it.
    """
    from alleleforge.report.builder import build_report, model_limitation_lines
    from alleleforge.report.html import render_html
    from alleleforge.report.pdf import render_pdf

    report = build_report(ancestry_menu)
    lines = model_limitation_lines(report.provenance)

    assert len(lines) == 1, "only the model that documents limits should produce a line"
    assert lines[0].startswith("cas9-efficiency-ensemble 0.1 — ")
    assert "not for: Clinical decision-making" in lines[0]
    assert "known failure modes: Poorly calibrated below 20% GC" in lines[0]
    # indelphi documents neither, so it must not appear with an empty limitation.
    assert "indelphi" not in lines[0]

    html = render_html(report)
    assert "Model limitations" in html
    assert "Clinical decision-making" in html
    pdf = render_pdf(report)
    assert b"MODEL LIMITATIONS" in pdf
    assert b"Clinical decision-making" in pdf


def test_a_card_with_no_documented_limits_prints_no_section() -> None:
    """An empty heading is worse than no heading: it reads as "no known limits"."""
    from alleleforge.report.builder import model_limitation_lines
    from alleleforge.types.provenance import ModelCheckpoint, Provenance

    bare = Provenance(
        alleleforge_version="0.0.0",
        seed=1,
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        models=(ModelCheckpoint(name="m", version="1"),),
    )
    assert model_limitation_lines(bare) == []
    assert model_limitation_lines(None) == []


def test_a_truncated_outcome_table_says_it_is_truncated(ancestry_menu: RankedMenu) -> None:
    """`P(intended) = 0.87` above three rows of 0.069 looks like an error. It is a tail.

    A knock-out's NHEJ spectrum is dozens of alleles; the table shows the top three by
    default, so the visible rows summed to 0.18 while the headline said 0.87 — with
    nothing saying the table was truncated. The candidate list has said "Showing 50 of
    470" since it was capped; the outcome table made the same omission.
    """
    from alleleforge.report.builder import build_report
    from alleleforge.report.html import render_html
    from alleleforge.report.pdf import render_pdf

    report = build_report(ancestry_menu, top_alleles=1)
    candidate = report.candidates[0]
    assert candidate.n_outcome_alleles > len(candidate.outcome_top), (
        "fixture is not truncated — the assertions below would be vacuous"
    )
    assert candidate.outcome_shown_mass == pytest.approx(
        sum(a.probability for a in candidate.outcome_top)
    )

    html = render_html(report)
    assert f"showing 1 of {candidate.n_outcome_alleles} predicted alleles" in html
    assert b"showing 1 of" in render_pdf(report)


def test_a_complete_outcome_table_says_nothing(ancestry_menu: RankedMenu) -> None:
    """A note on every table is noise; it must track the actual truncation."""
    from alleleforge.report.builder import build_report
    from alleleforge.report.html import render_html

    report = build_report(ancestry_menu, top_alleles=50)
    candidate = report.candidates[0]
    assert candidate.n_outcome_alleles == len(candidate.outcome_top)
    assert "predicted alleles (" not in render_html(report)


def test_a_report_says_which_coordinate_base_its_loci_are_in(prime_menu: RankedMenu) -> None:
    """A printed cut site is the number a reader pastes into a genome browser.

    AlleleForge is uniformly 0-based half-open — in at `--region`, out at every
    printed locus — and no user-facing surface said so. IGV, UCSC and samtools all
    read `chr7:100-200` as 1-based inclusive, so the same digits name a different
    base there, and the declared egress converter (`GenomicInterval.to_one_based`)
    had no callers anywhere in the tree. The convention is fine; its silence was not.
    """
    from alleleforge.report.builder import COORDINATE_NOTE, provenance_lines
    from alleleforge.report.html import render_html
    from alleleforge.types.provenance import Provenance

    prov = Provenance(
        alleleforge_version="9.9.9",
        reference_build="hg38",
        seed=7,
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    assert COORDINATE_NOTE in provenance_lines(prov)
    assert "0-based half-open" in COORDINATE_NOTE
    # ...and it reaches the rendered page, not just the helper.
    assert "0-based half-open" in render_html(build_report(prime_menu))


def test_the_region_option_states_its_coordinate_base() -> None:
    """`--variant` said "1-based pos as in a VCF"; `--region` said nothing.

    Two loci options on one command line, in two different coordinate systems, with
    only one of them labelled — a reader carries the stated base onto the silent one.
    """
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    help_text = CliRunner().invoke(app, ["design", "--help"]).output
    assert "1-based" in help_text  # --variant / --pop-freqs, as before
    assert "0-based half-open" in help_text  # --region, which said nothing
