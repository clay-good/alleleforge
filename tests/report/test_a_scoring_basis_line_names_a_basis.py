"""The "scoring basis" line is printed only when there is a basis to name.

The printable sheet writes, under a candidate's off-target count:

    if c.n_offtarget_sites is not None and (c.offtarget_scorer or c.offtarget_matrix):

Both reads are satisfied together by every fixture in the suite — a searched candidate
carries its scorer and its matrix — so the second had no case of its own. A search can
report a count with neither recorded: the Cas12a and MIT paths set one or the other, a
cached report from an older run may carry neither, and `offtarget_scorer` is optional on
the model. Without that read the sheet prints

    scoring basis:

with nothing after the colon — on the page a reader uses to decide how much to trust a
specificity number, in the field whose whole job is to say what produced it. This
project has twice repaired a score that did not say what scored it; a blank label is the
same failure with better punctuation.
"""

from __future__ import annotations

import pytest

from alleleforge.report.builder import CandidateReport
from alleleforge.report.pdf import _candidate_lines
from alleleforge.types.edit import Chemistry


def _candidate(**overrides: object) -> CandidateReport:
    base: dict[str, object] = {
        "rank": 1,
        "chemistry": Chemistry.PRIME,
        "on_pareto_front": True,
        "reagent": "pegRNA candidate 1",
        "efficiency": None,
        "bystander_burden": None,
        "p_intended": None,
        "outcome_top": (),
        "n_offtarget_sites": 3,
        "offtarget_specificity": None,
        "offtarget_by_ancestry": (),
        "oligos": None,
        "flags": (),
        "rationale": None,
    }
    return CandidateReport(**{**base, **overrides})  # type: ignore[arg-type]


def _basis_lines(candidate: CandidateReport) -> list[str]:
    return [line for line in _candidate_lines(candidate) if "scoring basis:" in line]


def test_a_searched_candidate_with_no_recorded_basis_prints_no_basis_line() -> None:
    assert _basis_lines(_candidate()) == []


@pytest.mark.parametrize("field", ["offtarget_scorer", "offtarget_matrix"])
def test_either_half_on_its_own_is_enough_to_name_one(field: str) -> None:
    """The positive case, for each half, so the check above is not passing by silence."""
    lines = _basis_lines(_candidate(**{field: "CFD"}))
    assert len(lines) == 1, lines
    assert lines[0].strip().removeprefix("scoring basis:").strip(), lines


def test_an_unsearched_candidate_prints_no_basis_line() -> None:
    """The other read, which did have a case; kept so the pair stays visible."""
    assert _basis_lines(_candidate(n_offtarget_sites=None, offtarget_scorer="CFD")) == []
