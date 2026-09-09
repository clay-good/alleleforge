"""No field may show a value for something that was never computed.

`0.0` in a worst-case column and `1.0` in a specificity column are the *reassuring*
values. A candidate that was never off-target-searched must not produce either, on any
surface, because a reader scanning a column cannot tell a measured zero from an unmeasured
one — and this project has already shipped that exact confusion (`worst_offtarget: 0.0`
for a candidate with no report).

The field list is derived from `CandidateReport` rather than written out, so an off-target
field added later is covered the day it appears. That is the part a hand-written test
misses: the invariant is not about today's seven columns.

Derived **by name**, though — `"offtarget" in field` — which is a proxy for the real
population, not the population. The two ancestry columns the flat exports carry are called
`worst_ancestry` and `worst_ancestry_score`; they are off-target-derived and neither name
contains the substring, so both sat outside every check in this file. Turning an unmeasured
`worst_ancestry_score` into `0.0` — the most reassuring value a worst-case column can hold,
in the two tables a pipeline filters on — left the whole suite green: 3,291 passed.

The same question, asked of the *prediction* columns rather than the search ones, gave the
same answer. Twelve of them are renamed or derived on the way into the table —
`efficiency_low`, `in_distribution`, `calibrated`, and the bystander and p_intended
variants — and `_row`'s own comment says what depends on it: the columns are blank for an
absent prediction, "which is the difference between 'no interval was computed' and 'the
interval is zero-width'". Making an absent prediction render `in_distribution: True`,
`calibrated: True`, `efficiency_low: 0.0` or `efficiency_high: 1.0` — the reassuring value
in each case — left 3,294 tests passing, one mutation at a time and two together.

The safety *score* is the deliberate exception, documented in `ranking._safety`: an
unsearched candidate scores 1.0 because penalising an unmeasured axis is a policy this
project has no basis for. What makes that honest is the `offtarget-not-searched` flag
travelling in the same row, so this test pins the flag rather than the number.
"""

from __future__ import annotations

from alleleforge.report.builder import CandidateReport, build_report
from alleleforge.report.export import report_to_json, report_to_tsv
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
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

#: Fields of the rendered candidate that describe the off-target search.
_OFFTARGET_FIELDS = sorted(f for f in CandidateReport.model_fields if "offtarget" in f)


def _unsearched_menu() -> RankedMenu:
    guide = Guide(
        spacer=Spacer(sequence=DNASequence("ACGTAACGTTACGTAACGTT")),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        offtarget=None,
        flags=("offtarget-not-searched",),
        rationale="no search was run",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def _searched_menu() -> RankedMenu:
    """The same candidate, with a search that ran *and* carried ancestry frequencies.

    The ancestry half matters: without a population source `worst_ancestry_score` is
    `None` even on a searched candidate, so a population built from a plain searched
    report would not contain the columns this file exists for.
    """
    guide = Guide(
        spacer=Spacer(sequence=DNASequence("ACGTAACGTTACGTAACGTT")),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )
    site = OffTargetSite(
        locus=GenomicInterval(chrom="chr1", start=500, end=520, strand=Strand.PLUS),
        mismatches=2,
        score=0.42,
        score_method=ScoreMethod.CFD,
        origin=SiteOrigin.POPULATION,
        populations=("afr", "nfe"),
        frequency=0.05,
        ancestries={"afr": 0.09, "nfe": 0.001},
        causal_allele="chr1:505:T>G",
        pam_sequence="TGG",
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        offtarget=OffTargetReport(
            spacer="ACGTAACGTTACGTAACGTT",
            pam="NGG",
            sites=(site,),
            searched_bases=4000,
            resolved_bases=4000,
            scorer="CFD",
            score_matrix="doench-2016-cfd",
            available_populations=("afr", "nfe"),
            maf_threshold=0.001,
        ),
        rationale="a search that found something",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def _tsv_row(menu: RankedMenu) -> dict[str, str]:
    lines = [
        line for line in report_to_tsv(build_report(menu)).splitlines() if not line.startswith("#")
    ]
    return dict(zip(lines[0].split("\t"), lines[1].split("\t"), strict=True))


#: Flat-export columns whose value comes from the off-target search. Written out, and kept
#: honest by the three checks below rather than by trust: a column here must be populated
#: on the searched fixture, must be empty on the unsearched one, and no column that tells
#: the two fixtures apart may be missing from the list.
_SEARCH_DERIVED_COLUMNS: tuple[str, ...] = (
    "n_offtarget_sites",
    "offtarget_specificity",
    "offtarget_expected_burden",
    "offtarget_scorer",
    "offtarget_matrix",
    "offtarget_scorer_citation",
    "offtarget_search",
    "worst_ancestry",
    "worst_ancestry_score",
)


def test_every_listed_column_is_one_a_search_actually_fills() -> None:
    """A column listed here that no search populates is a line nobody is checking."""
    searched = _tsv_row(_searched_menu())
    unfilled = sorted(c for c in _SEARCH_DERIVED_COLUMNS if searched.get(c, "") == "")
    assert not unfilled, (
        f"listed as search-derived but empty even after a search with ancestry data: {unfilled}"
    )


def test_the_list_covers_every_column_the_search_changes() -> None:
    """Completeness, derived: any column that tells the two fixtures apart belongs here.

    This is what would have caught the ancestry pair without anyone thinking of them.
    """
    searched = _tsv_row(_searched_menu())
    unsearched = _tsv_row(_unsearched_menu())
    differing = {
        column
        for column, value in searched.items()
        if value != "" and unsearched.get(column, "") == ""
    }
    missing = sorted(differing - set(_SEARCH_DERIVED_COLUMNS))
    assert not missing, (
        f"these columns are filled by a search and absent without one, and are not listed "
        f"as search-derived: {missing}"
    )


def test_no_column_a_search_fills_carries_a_value_when_none_ran() -> None:
    """The same rule over the columns a pipeline actually reads, renames included."""
    unsearched = _tsv_row(_unsearched_menu())
    for column in _SEARCH_DERIVED_COLUMNS:
        assert unsearched.get(column, "") == "", (
            f"{column} rendered {unsearched[column]!r} for a candidate that was never "
            "searched. A reader cannot tell it from a measured result, and in a "
            "worst-case column the unmeasured value is the reassuring one."
        )


def test_the_field_list_is_not_empty() -> None:
    """Derived, so it must be checked for vacuity before it proves anything."""
    assert len(_OFFTARGET_FIELDS) >= 5, _OFFTARGET_FIELDS


def test_no_offtarget_field_carries_a_value() -> None:
    rendered = build_report(_unsearched_menu()).candidates[0]
    for name in _OFFTARGET_FIELDS:
        value = getattr(rendered, name)
        assert value is None or value == () or value == [], (
            f"{name} is {value!r} for a candidate that was never searched; a number here "
            "is indistinguishable from a measured result"
        )


def test_the_tsv_leaves_those_columns_empty() -> None:
    report = build_report(_unsearched_menu())
    lines = [line for line in report_to_tsv(report).splitlines() if not line.startswith("#")]
    row = dict(zip(lines[0].split("\t"), lines[1].split("\t"), strict=True))
    for name in _OFFTARGET_FIELDS:
        if name in row:
            assert row[name] == "", f"{name} rendered {row[name]!r} with nothing searched"


def test_the_json_export_does_not_invent_zeroes() -> None:
    body = report_to_json(build_report(_unsearched_menu()))
    for name in _OFFTARGET_FIELDS:
        assert f'"{name}": 0' not in body
        assert f'"{name}": 1.0' not in body


def test_the_row_says_the_axis_was_not_measured() -> None:
    """The safety score is 1.0 by policy; the flag beside it is what makes that honest."""
    rendered = build_report(_unsearched_menu()).candidates[0]
    assert "offtarget-not-searched" in rendered.flags


# --- the same rule for a prediction that was never computed ----------------------


def _unpredicted_menu() -> RankedMenu:
    """A candidate carrying no efficiency, outcome or bystander prediction.

    Not hypothetical: `_row` is written for it — every prediction column is `None if
    <prediction> is None else ...` — and its comment says the blank is "the difference
    between 'no interval was computed' and 'the interval is zero-width'".
    """
    guide = Guide(
        spacer=Spacer(sequence=DNASequence("ACGTAACGTTACGTAACGTT")),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        efficiency=None,
        p_intended=None,
        bystander_burden=None,
        offtarget=None,
        flags=("offtarget-not-searched",),
        rationale="nothing was predicted",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def _predicted_menu() -> RankedMenu:
    """The same candidate with all three predictions present."""
    guide = Guide(
        spacer=Spacer(sequence=DNASequence("ACGTAACGTTACGTAACGTT")),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="chr1", start=10, end=30, strand=Strand.PLUS),
        cut_site=27,
    )
    prediction = Prediction[float](
        value=0.5,
        interval=(0.35, 0.65),
        interval_level=0.80,
        method=UncertaintyMethod.HEURISTIC,
        in_distribution=True,
        calibrated=False,
    )
    candidate = DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=guide,
        efficiency=prediction,
        # `p_intended` reaches the report only through `outcome` — the builder reads
        # `candidate.outcome.p_intended` — so a fixture with the prediction and no
        # outcome leaves all five p_intended columns blank and silently drops them
        # from the population below.
        outcome=EditOutcome(
            alleles=(
                AlleleOutcome(allele="intended", probability=0.6, is_intended=True),
                AlleleOutcome(allele="indel", probability=0.4, is_intended=False),
            )
        ),
        p_intended=prediction,
        bystander_burden=prediction,
        offtarget=None,
        flags=("offtarget-not-searched",),
        rationale="everything was predicted",
    )
    return RankedMenu(candidates=(candidate,), rationale="fixture")


def test_the_two_prediction_fixtures_differ() -> None:
    """Or the completeness check below has nothing to derive a population from."""
    assert _tsv_row(_predicted_menu()) != _tsv_row(_unpredicted_menu())


#: Flat-export columns whose value comes from a prediction. Written out for the same
#: reason `_SEARCH_DERIVED_COLUMNS` is: deriving the population as "filled when predicted
#: and empty when not" is circular — a writer that starts filling a column *without* a
#: prediction drops that column out of its own population, and the check it should have
#: failed never runs on it.
_PREDICTION_DERIVED_COLUMNS: tuple[str, ...] = (
    "efficiency",
    "efficiency_low",
    "efficiency_high",
    "in_distribution",
    "calibrated",
    "bystander_burden",
    "bystander_burden_low",
    "bystander_burden_high",
    "bystander_burden_in_distribution",
    "bystander_burden_calibrated",
    "p_intended",
    "p_intended_low",
    "p_intended_high",
    "p_intended_in_distribution",
    "p_intended_calibrated",
)


def test_every_listed_prediction_column_is_one_a_prediction_fills() -> None:
    """A column listed here that no prediction populates is a line nobody is checking."""
    predicted = _tsv_row(_predicted_menu())
    unfilled = sorted(c for c in _PREDICTION_DERIVED_COLUMNS if predicted.get(c, "") == "")
    assert not unfilled, f"listed as prediction-derived but empty when predicted: {unfilled}"


def test_the_prediction_list_covers_every_column_a_prediction_changes() -> None:
    """Completeness, derived — the half that finds a column nobody thought of."""
    predicted = _tsv_row(_predicted_menu())
    unpredicted = _tsv_row(_unpredicted_menu())
    differing = {
        column
        for column, value in predicted.items()
        if value != "" and unpredicted.get(column, "") == ""
    }
    missing = sorted(differing - set(_PREDICTION_DERIVED_COLUMNS) - set(_SEARCH_DERIVED_COLUMNS))
    assert not missing, f"filled by a prediction and not listed as prediction-derived: {missing}"


def test_no_column_a_prediction_fills_carries_a_value_without_one() -> None:
    """`in_distribution: True` for something never predicted is the reassuring value."""
    unpredicted = _tsv_row(_unpredicted_menu())
    for column in _PREDICTION_DERIVED_COLUMNS:
        assert unpredicted.get(column, "") == "", (
            f"{column} rendered {unpredicted[column]!r} for a candidate with no "
            "prediction — indistinguishable from a computed one"
        )


def test_the_prediction_columns_include_the_flags_a_reader_trusts() -> None:
    """Named explicitly: these four are booleans, so an invented value is a *claim*
    about the evidence rather than an obviously-odd number."""
    predicted = _tsv_row(_predicted_menu())
    unpredicted = _tsv_row(_unpredicted_menu())
    for column in (
        "in_distribution",
        "calibrated",
        "p_intended_in_distribution",
        "bystander_burden_calibrated",
    ):
        assert predicted[column] != "", f"{column} is empty even with a prediction"
        assert unpredicted[column] == "", (
            f"{column} says {unpredicted[column]!r} about a prediction that does not exist"
        )
