"""The cohort TSV carried Python reprs and raw float noise.

Found by running `aforge batch --summary-tsv` and reading the file as a data consumer.
The rows held:

    best_caveats            ['pol3-terminator', 'gc-out-of-band:0.20']
    offtarget_sources       {}
    best_efficiency_low     0.44999999999999996

`_batch_tsv` passed every value through `str()`, so a list became a Python list literal
— quotes, brackets, `, ` separators — inside a tab-separated file, and a float arrived
with seventeen significant digits of binary noise. `report/export.py`, this project's
*other* TSV, formats before it renders: four decimal places, flags joined with `;`.

One project, one format, two conventions, and only one of them is readable without a
Python parser. This pins the cohort side to the report side's conventions.
"""

from __future__ import annotations

from alleleforge.cli.main import _batch_tsv


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "item_id": "chr2:1006:G>A",
        "variant": "chr2:1005:G>A",
        "status": "ok",
        "best_chemistry": "base_abe",
        "best_efficiency": 0.6,
        "best_efficiency_low": 0.44999999999999996,
        "best_efficiency_high": 0.75,
        "best_efficiency_in_distribution": True,
        "best_caveats": ["pol3-terminator", "gc-out-of-band:0.20"],
        "offtarget_sources": {},
        "best_bystander_burden": 0.0,
        "worst_offtarget": None,
        "best_specificity": 0.9507042253989784,
        "n_candidates": 1,
        "no_candidate_reason": None,
        "error": None,
    }
    row.update(overrides)
    return row


def _cells(text: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    header, first = lines[0].split("\t"), lines[1].split("\t")
    return dict(zip(header, first, strict=True))


def test_a_list_is_delimited_not_a_python_literal() -> None:
    cells = _cells(_batch_tsv([_row()]))
    assert cells["best_caveats"] == "pol3-terminator;gc-out-of-band:0.20"
    assert "[" not in cells["best_caveats"] and "'" not in cells["best_caveats"]


def test_an_empty_collection_is_an_empty_cell() -> None:
    """`[]` is a value a consumer has to special-case; blank is not."""
    cells = _cells(_batch_tsv([_row(best_caveats=[])]))
    assert cells["best_caveats"] == ""


def test_a_searched_row_never_looks_like_an_unsearched_one() -> None:
    """The one column where blanking an empty collection would lose a fact.

    `offtarget_sources` names the *optional* safety sources. `None` means no off-target
    report exists; `{}` means one does and no optional source was supplied. Rendering
    both as an empty cell would collapse "we did not look" into "we looked and there was
    nothing to add" — on the axis where that confusion is the dangerous one. Caught by
    re-reading a real file after the rendering change that introduced it.
    """
    searched = _cells(_batch_tsv([_row(offtarget_sources={}, worst_offtarget=0.0)]))
    unsearched = _cells(_batch_tsv([_row(offtarget_sources=None, worst_offtarget=None)]))
    assert searched["offtarget_sources"] == "reference-only"
    assert unsearched["offtarget_sources"] == ""
    assert searched["offtarget_sources"] != unsearched["offtarget_sources"]


def test_a_populated_mapping_is_readable() -> None:
    cells = _cells(_batch_tsv([_row(offtarget_sources={"gnomad": 3, "reference": 1})]))
    assert cells["offtarget_sources"] == "gnomad=3;reference=1"


def test_floats_are_rounded_like_the_report_export() -> None:
    cells = _cells(_batch_tsv([_row()]))
    assert cells["best_efficiency_low"] == "0.45"
    assert cells["best_specificity"] == "0.9507"


def test_a_bool_is_not_rendered_as_a_number() -> None:
    """A bool is an int in Python; the float branch must not claim it."""
    cells = _cells(_batch_tsv([_row(best_efficiency_in_distribution=False)]))
    assert cells["best_efficiency_in_distribution"] == "False"


def test_none_is_still_empty_and_delimiters_are_still_neutralized() -> None:
    cells = _cells(_batch_tsv([_row(worst_offtarget=None, error="bad\tinput\nhere")]))
    assert cells["worst_offtarget"] == ""
    assert cells["error"] == "bad input here"
