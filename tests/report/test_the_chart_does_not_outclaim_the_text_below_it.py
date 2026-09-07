"""The chart said *Calibrated efficiency*. Nothing on the page was calibrated.

The per-candidate text is meticulous about this. Every efficiency prints

    Efficiency 0.78 [0.66, 0.90] @ 80% (nominal — coverage not measured)
                                       (heuristic point estimate — not from a trained model)

because with the bundled models `calibrated` is `False` and `point_from_trained_model`
is `False`. Directly above all of it sat a bar chart with the fixed title *Calibrated
efficiency* — the first thing a reader looks at, asserting the opposite of every line
beneath it. The honesty machinery reached the prose and stopped at the figure, which is
the recurring shape: the mechanism built to prevent a defect is where the defect lives.

The title now follows the bars, and the subtitle carries the same qualifiers the text
does, quantified when only some bars are affected — a report mixing a trained prime
scorer with the heuristic Cas9 one must not be described by either extreme.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.html import _efficiency_subtitle, _efficiency_title, render_html
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.prediction import Prediction, UncertaintyMethod


def _chart_text(html: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", html)


def _prediction(*, calibrated: bool, trained: bool, in_distribution: bool = True) -> Prediction:
    """Build a prediction, using the one authorized path to ``calibrated=True``.

    `Prediction(calibrated=True)` is coerced back to `False` on purpose — only a fitted
    calibrator may certify one — so a test that wants the calibrated case has to go
    through `calibrated_by`, and this helper asserts it actually got what it asked for.
    """
    kwargs = {
        "value": 0.5,
        "interval": (0.3, 0.7),
        "interval_level": 0.8,
        "method": UncertaintyMethod.CONFORMAL if calibrated else UncertaintyMethod.HEURISTIC,
        "point_from_trained_model": trained,
        "in_distribution": in_distribution,
    }
    prediction = Prediction.calibrated_by(**kwargs) if calibrated else Prediction(**kwargs)
    assert prediction.calibrated is calibrated
    return prediction


def test_the_shipped_report_does_not_call_its_numbers_calibrated(
    prime_menu: RankedMenu,
) -> None:
    """The defect, end to end: the bundled models calibrate nothing."""
    report = build_report(prime_menu)
    assert any(c.efficiency is not None for c in report.candidates), "no bars to plot"
    assert all(
        not c.efficiency.calibrated for c in report.candidates if c.efficiency is not None
    ), "the fixture no longer exercises the uncalibrated case"

    texts = _chart_text(render_html(report))
    assert "Calibrated efficiency" not in texts
    assert "Predicted efficiency" in texts


def test_the_subtitle_carries_the_same_qualifiers_the_text_does(
    prime_menu: RankedMenu,
) -> None:
    # Joined: the subtitle is word-wrapped across `<text>` lines so it stays inside the
    # plot width, so a qualifier can straddle two of them.
    subtitle = " ".join(
        t for t in _chart_text(render_html(build_report(prime_menu))) if len(t) > 12
    )
    assert "coverage not measured" in subtitle
    assert "not from a trained model" in subtitle


def test_a_fully_calibrated_chart_may_say_so() -> None:
    """The title is not just pessimistic — it tracks the bars."""
    plotted = [_prediction(calibrated=True, trained=True)] * 3
    assert _efficiency_title(plotted) == "Calibrated efficiency"
    subtitle = _efficiency_subtitle(plotted)
    assert "coverage not measured" not in subtitle
    assert "not from a trained model" not in subtitle


@pytest.mark.parametrize(
    "calibrated_count, expected",
    [(0, "Predicted efficiency"), (2, "Predicted efficiency"), (3, "Calibrated efficiency")],
)
def test_a_mixed_chart_is_not_described_by_either_extreme(
    calibrated_count: int, expected: str
) -> None:
    plotted = [_prediction(calibrated=True, trained=True) for _ in range(calibrated_count)]
    plotted += [_prediction(calibrated=False, trained=False) for _ in range(3 - calibrated_count)]
    assert _efficiency_title(plotted) == expected
    subtitle = _efficiency_subtitle(plotted)
    if 0 < calibrated_count < 3:
        # Scoped, not blanket: "intervals are nominal" would libel the calibrated bars.
        assert f"{3 - calibrated_count} of 3 bars" in subtitle, subtitle


def test_an_out_of_distribution_bar_is_named_too() -> None:
    """`calibrated=True` is unreachable here by design: an OOD prediction is not one."""
    plotted = [_prediction(calibrated=False, trained=True, in_distribution=False)]
    assert "out-of-distribution" in _efficiency_subtitle(plotted)
