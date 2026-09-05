"""The HTML render's candidate cap, and the guarantee it must not break.

A prime design routinely yields several hundred candidates — every PBS x
RTT-homology x PAM combination is a distinct pegRNA — so an uncapped
"self-contained" page runs to megabytes. Capping is a presentation decision, and
it carries two obligations: say so on the page, and never let the cap decide away
a **Pareto-front** candidate. The front is the report's entire answer to "I weight
the objectives differently from your defaults"; a candidate that is optimal on
safety but 200th on the composite score is precisely the one such a reader came
for.
"""

from __future__ import annotations

from alleleforge.report.builder import CandidateReport, DesignReport
from alleleforge.report.html import DEFAULT_HTML_CANDIDATES, _visible, render_html
from alleleforge.types.edit import Chemistry


def _candidate(rank: int, *, pareto: bool) -> CandidateReport:
    return CandidateReport(
        rank=rank,
        chemistry=Chemistry.PRIME,
        on_pareto_front=pareto,
        reagent=f"pegRNA candidate {rank}",
        efficiency=None,
        bystander_burden=None,
        p_intended=None,
        outcome_top=(),
        n_offtarget_sites=None,
        offtarget_specificity=None,
        offtarget_by_ancestry=(),
        oligos=None,
        flags=(),
        rationale=None,
    )


def _report(n: int, pareto_ranks: set[int]) -> DesignReport:
    return DesignReport(
        title="t",
        disclaimer="d",
        variant=None,
        intent=None,
        weights={},
        candidates=tuple(_candidate(i, pareto=i in pareto_ranks) for i in range(1, n + 1)),
        provenance=None,
    )


def test_a_far_ranked_pareto_candidate_survives_the_cap() -> None:
    report = _report(300, pareto_ranks={1, 200, 297})
    shown, withheld = _visible(report, DEFAULT_HTML_CANDIDATES)
    ranks = {c.rank for c in shown}
    assert {200, 297} <= ranks, "the cap dropped a Pareto-front candidate"
    assert len(shown) == DEFAULT_HTML_CANDIDATES + 2
    assert withheld == 300 - len(shown)
    assert [c.rank for c in shown] == sorted(ranks), "rank order must survive"


def test_the_render_states_what_it_withheld() -> None:
    html = render_html(_report(300, pareto_ranks={1}))
    assert "Showing 50 of 300 candidates" in html
    assert "250 are in the lossless JSON/CSV export" in html


def test_no_cap_note_when_nothing_is_withheld() -> None:
    html = render_html(_report(10, pareto_ranks={1}))
    assert "Showing" not in html
    assert "candidate 10" in html


def test_explicit_none_renders_everything() -> None:
    report = _report(120, pareto_ranks={1})
    shown, withheld = _visible(report, None)
    assert len(shown) == 120
    assert withheld == 0
    assert "candidate 120" in render_html(report, max_candidates=None)
