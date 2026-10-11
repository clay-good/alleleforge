"""The printable report prints an interval's bounds in the order a reader assumes.

Three lines on the order sheet carry a predictive interval — efficiency, bystander
burden, and P(intended) — and each writes it as
`f"[{p.interval[0]:.2f}, {p.interval[1]:.2f}]"`. A constant pass turned every one of those
`interval[0]`s into `interval[1]` and the suite stayed green: no test had ever read the
rendered interval text. The page would then print `[0.57, 0.57]` for a prediction whose
real band is `[0.42, 0.57]`, quoting the upper bound as the lower and collapsing the
band's width to zero — a report that looks more certain than the model is. This project
has already found exactly this defect once, in the ranking rationale; nothing was checking
for it here.

The fixture needs an interval whose two bounds differ, or swapping them changes nothing
and the test measures nothing. That premise is asserted first.
"""

from __future__ import annotations

import re

from alleleforge.report.builder import build_report
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import RankedMenu
from tests.pdf_text import pdf_text

_INTERVAL = re.compile(r"\[(-?\d+\.\d+), (-?\d+\.\d+)\]")


def _rendered(menu: RankedMenu) -> str:
    return pdf_text(render_pdf(build_report(menu, variant="chr2:70:A>C")))


def test_the_bystander_burden_interval_prints_its_lower_bound_first(
    abe_menu: RankedMenu,
) -> None:
    """A base-editor menu, because only that chemistry carries a bystander burden.

    The prime fixture never reaches this line at all: a pegRNA has no bystander
    burden, so the whole bystander branch is dead for it and a test built on the
    prime menu leaves this interval unmeasured however it is rendered.
    """
    report = build_report(abe_menu, variant="chr2:70:A>C")
    candidate = next((c for c in report.candidates if c.bystander_burden is not None), None)
    assert candidate is not None, "the ABE fixture must yield a bystander burden"
    prediction = candidate.bystander_burden
    assert prediction is not None
    low, high = prediction.interval
    assert low < high, "a zero-width band cannot distinguish the two bounds"

    text = _rendered(abe_menu)
    expected = f"bystander burden {prediction.value:.2f} [{low:.2f}, {high:.2f}]"
    assert expected in text, (
        f"the rendered bystander-burden line does not read {expected!r}; "
        f"nearest interval on the page: {_INTERVAL.findall(text)[:3]}"
    )


def test_the_efficiency_interval_prints_its_lower_bound_first(
    prime_menu: RankedMenu,
) -> None:
    report = build_report(prime_menu, variant="chr2:70:A>C")
    prediction = report.candidates[0].efficiency
    assert prediction is not None
    low, high = prediction.interval
    assert low < high, "a zero-width band cannot distinguish the two bounds"

    text = _rendered(prime_menu)
    expected = f"efficiency {prediction.value:.2f} [{low:.2f}, {high:.2f}]"
    assert expected in text, (
        f"the rendered efficiency line does not read {expected!r}; "
        f"nearest interval on the page: {_INTERVAL.findall(text)[:3]}"
    )


def test_no_printed_interval_has_its_bounds_the_wrong_way_round(
    prime_menu: RankedMenu,
) -> None:
    """Every bracketed pair on the page, not just the one line above."""
    text = _rendered(prime_menu)
    pairs = [(float(a), float(b)) for a, b in _INTERVAL.findall(text)]
    assert pairs, "no interval was rendered at all; this test would pass vacuously"
    inverted = [(a, b) for a, b in pairs if a > b]
    assert not inverted, f"intervals printed high-then-low: {inverted}"


def test_at_least_one_printed_interval_has_a_real_width(
    prime_menu: RankedMenu,
) -> None:
    """The negative case for the test above: all-equal pairs would also pass it."""
    text = _rendered(prime_menu)
    pairs = [(float(a), float(b)) for a, b in _INTERVAL.findall(text)]
    assert any(a < b for a, b in pairs), (
        "every rendered interval has zero width, so a collapsed band would be "
        "indistinguishable from a correct one"
    )


def test_the_p_intended_interval_prints_low_to_high(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu, variant="chr2:70:A>C")
    candidate = next((c for c in report.candidates if c.p_intended_prediction is not None), None)
    if candidate is None:  # pragma: no cover - fixture-dependent
        return
    prediction = candidate.p_intended_prediction
    assert prediction is not None
    low, high = prediction.interval
    text = _rendered(prime_menu)
    assert f"P(intended) = {prediction.value:.2f} [{low:.2f}, {high:.2f}]" in text
