"""The calibration study printed a Python `None` in a column of numbers.

`docs`-facing artifacts are where this project's honesty either holds or does not, and
the calibration study is the one it offers as its calibration evidence — the file that
opens by saying every number in it comes from synthetic stand-ins.

Once a metric could be genuinely undefined, two of its consumers had no concept of the
absence their own data source produces:

* the study's per-task table rendered the value with an f-string, so the cell read
  `None` — which says nothing a reader can act on, and reads as a bug rather than as a
  statement about what was measured; and
* `task_ece_figure` called `float()` on the ECE, so the one chart in the set whose
  subject is honest calibration would have crashed on an honestly-absent calibration.
  Had it not crashed, a bar at zero on that chart reads as *perfectly calibrated*.

Both are checked here against a table with a hole punched in it, because the shipped
fixtures happen to define every ECE today — which is exactly how a consumer comes to be
written without the case.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from alleleforge.benchmark import calibration


def _holed(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Return the real table with one task's ECE and primary value removed."""
    rows = calibration.task_calibration_table()
    assert rows and any(r["ece"] is not None for r in rows), rows
    rows[0] = {**rows[0], "ece": None, "primary_value": None}
    rows[0].setdefault("primary_undefined_reason", "the fixture for this test")
    rows[0]["primary_undefined_reason"] = "the model predicted one constant value"
    return rows


def test_the_table_prints_the_word_not_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.calibration_study as study

    rows = _holed(monkeypatch)
    markdown = study.render_markdown(rows, calibration.generalization_table(), [])

    # The task appears in two tables (per-task calibration, then the generalization
    # gap); both are rendered by this function and neither may print a repr.
    task_rows = [line for line in markdown.splitlines() if line.startswith(f"| {rows[0]['task']} ")]
    assert task_rows, markdown
    for row in task_rows:
        assert "None" not in row, row
    assert any("undefined" in row for row in task_rows), task_rows
    # And the reason travels with it: a hole in a table is only useful if the reader
    # learns what would have filled it.
    assert "the model predicted one constant value" in markdown, markdown


def test_the_figure_draws_no_bar_for_an_absent_ece(monkeypatch: pytest.MonkeyPatch) -> None:
    from alleleforge.viz import figures

    rows = _holed(monkeypatch)
    monkeypatch.setattr(figures, "task_calibration_table", lambda: rows)
    svg = figures.task_ece_figure()  # would have raised TypeError on float(None)

    assert svg.startswith("<svg"), svg[:40]
    # The subtitle is wrapped across several `<text>` elements, so read the drawing's
    # text content rather than its markup.
    drawn = " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))
    assert f"No ECE for {rows[0]['task']}" in drawn, drawn[:400]
    for row in rows[1:]:
        assert str(row["task"]) in svg, row["task"]


def test_the_figure_still_draws_the_real_table() -> None:
    """The floor: without this, dropping every bar would satisfy the check above."""
    from alleleforge.viz import figures

    svg = figures.task_ece_figure()
    drawn = " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))
    assert "No ECE for" not in drawn, "the shipped fixtures define every ECE; this is a hole"
    for row in calibration.task_calibration_table():
        assert str(row["task"]) in svg
