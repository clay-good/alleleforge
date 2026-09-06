"""No off-target-derived field may show a value when nothing was searched.

`0.0` in a worst-case column and `1.0` in a specificity column are the *reassuring*
values. A candidate that was never off-target-searched must not produce either, on any
surface, because a reader scanning a column cannot tell a measured zero from an unmeasured
one — and this project has already shipped that exact confusion (`worst_offtarget: 0.0`
for a candidate with no report).

The field list is derived from `CandidateReport` rather than written out, so an off-target
field added later is covered the day it appears. That is the part a hand-written test
misses: the invariant is not about today's seven columns.

The safety *score* is the deliberate exception, documented in `ranking._safety`: an
unsearched candidate scores 1.0 because penalising an unmeasured axis is a policy this
project has no basis for. What makes that honest is the `offtarget-not-searched` flag
travelling in the same row, so this test pins the flag rather than the number.
"""

from __future__ import annotations

from alleleforge.report.builder import CandidateReport, build_report
from alleleforge.report.export import report_to_json, report_to_tsv
from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import Chemistry
from alleleforge.types.guide import PAM, Guide, Spacer
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
