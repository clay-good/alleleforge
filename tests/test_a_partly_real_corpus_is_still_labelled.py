"""A calibration report over a mixed corpus must label the rows that are stand-ins.

The banner and the figure caveat were both all-or-nothing: they fired when *every*
row was synthetic and vanished the moment one row was real. Real corpora arrive one
task at a time -- each dataset is blocked on a different upstream release -- so the
mixed table is the first one a reader sees, and it was the only one of the three
states that carried no warning at all. That is the dangerous direction: a table of
mostly fabricated numbers, with the caveat removed, read as a model's performance.
"""

from __future__ import annotations

from typing import Any

import scripts.calibration_study as study

from alleleforge.benchmark import calibration


def _task_row(name: str, *, synthetic: bool) -> dict[str, Any]:
    return {
        "task": name,
        "kind": "regression",
        "primary_metric": "spearman",
        "primary_value": 0.5,
        "primary_undefined_reason": "",
        "ece": 0.1,
        "n_test": 8,
        "synthetic": synthetic,
    }


def _gen_row(name: str, *, synthetic: bool, gap: float | None = 0.25) -> dict[str, Any]:
    return {
        "task": name,
        "metric": "spearman",
        "in_context": 0.6,
        "held_out": 0.35,
        "gap": gap,
        "undefined_reason": "" if gap is not None else "the baseline predicts one constant",
        "held_out_context": "HEK293",
        "synthetic": synthetic,
    }


def test_a_mixed_table_names_the_rows_that_are_stand_ins() -> None:
    rows = [_task_row("real-task", synthetic=False), _task_row("fake-task", synthetic=True)]
    md = study.render_markdown(rows, [], [])
    assert "SYNTHETIC" in md, "a table with fabricated rows must say so in prose"
    assert "`fake-task`" in md, "the banner must name the stand-in row"
    assert "1 of 2" in md, "the banner must say how much of the table is fabricated"
    assert "Every number below" not in md, "a real row must not be called fabricated"


def test_an_all_real_table_carries_no_caveat() -> None:
    md = study.render_markdown([_task_row("real-task", synthetic=False)], [], [])
    assert "SYNTHETIC" not in md
    assert "| real |" in md


def test_an_all_synthetic_table_keeps_the_blanket_banner() -> None:
    md = study.render_markdown([_task_row("fake-task", synthetic=True)], [], [])
    assert "Every number below is computed on the bundled SYNTHETIC" in md


def test_the_generalization_table_states_each_row_s_corpus() -> None:
    """A generalization gap is the claim most easily mistaken for a model measurement."""
    md = study.render_markdown(
        [],
        [_gen_row("fake-task", synthetic=True), _gen_row("real-task", synthetic=False)],
        [],
    )
    gen = md.split("## Cross-cell-type generalization gap", 1)[1]
    header = next(line for line in gen.splitlines() if line.startswith("| Task |"))
    assert header.rstrip().endswith("| Data |"), "the gap table needs a corpus column"
    fake = next(line for line in gen.splitlines() if "fake-task" in line)
    real = next(line for line in gen.splitlines() if "real-task" in line)
    assert fake.rstrip().endswith("| synthetic |")
    assert real.rstrip().endswith("| real |")


def test_an_undefined_gap_still_states_its_corpus() -> None:
    md = study.render_markdown([], [_gen_row("fake-task", synthetic=True, gap=None)], [])
    row = next(line for line in md.splitlines() if "fake-task" in line and "undefined" in line)
    assert row.rstrip().endswith("| synthetic |")


def test_the_shipped_generalization_rows_carry_the_flag_the_table_prints() -> None:
    """The flag was computed and never rendered; pin that it reaches the document."""
    rows = calibration.generalization_table()
    assert rows, "the bundled corpus has at least one stratified task"
    md = study.render_markdown([], rows, [])
    for r in rows:
        line = next(line for line in md.splitlines() if line.startswith(f"| {r['task']} |"))
        assert line.rstrip().endswith("| synthetic |" if r["synthetic"] else "| real |")
