"""The flat table listed reagents and never said what they were for.

`DesignReport` carries nine fields. The TSV and Parquet notes were built from two of
them — the disclaimer and the provenance block — so the one format a scientist opens in
a spreadsheet and forwards showed a ranked list of pegRNAs with no statement of the
variant they edit, the intent they were designed for, or the weights that produced the
`rank` column they are sorted by. All three sit on the HTML and PDF header line.

The `locus` column is not the missing fact: it says where each *guide* sits, which is a
different question from what the document is about, and an accession input makes the gap
obvious — the reader has a table of oligos and no locus anywhere that is the edit.

Pinned as a fact-by-surface table rather than three assertions, so a fact that stops
reaching one of the flat formats fails here. The needles come from the run's own data,
because a hand-written needle libels the surface it was not tuned on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.export import _export_notes, report_to_parquet, report_to_tsv
from alleleforge.types.candidate import RankedMenu

_VARIANT = "chr9:102:G>A"


@pytest.fixture
def report(prime_menu: RankedMenu) -> object:
    # The weights are not a `build_report` argument: they come off the menu's own
    # provenance snapshot, which is the point — they describe the run that produced the
    # `rank` column rather than anything the renderer chose.
    report = build_report(prime_menu, variant=_VARIANT, intent="knock_out")
    assert report.weights, "the fixture's menu carries no ranking weights to state"
    return report


@pytest.mark.parametrize(
    ("fact", "needle"),
    [
        ("the variant the table is about", _VARIANT),
        ("the intent it was designed for", "knock_out"),
        ("the weights that ordered the rank column", "ranking weights: efficiency"),
    ],
)
def test_the_tsv_states_the_fact(report: object, fact: str, needle: str) -> None:
    notes = [line for line in report_to_tsv(report).splitlines() if line.startswith("#")]
    assert any(needle in line for line in notes), (fact, notes)


@pytest.mark.parametrize(
    ("fact", "needle"),
    [
        ("the variant the table is about", _VARIANT),
        ("the intent it was designed for", "knock_out"),
        ("the weights that ordered the rank column", "ranking weights: efficiency"),
    ],
)
def test_the_parquet_states_the_fact(
    report: object, fact: str, needle: str, tmp_path: Path
) -> None:
    pl = pytest.importorskip("polars")
    raw = pl.read_parquet_metadata(report_to_parquet(report, tmp_path / "m.parquet"))
    notes = " ".join(v for k, v in raw.items() if k.startswith("note_"))
    assert needle in notes, (fact, notes)


def test_a_note_with_nothing_to_say_is_omitted_rather_than_stated_empty(
    prime_menu: RankedMenu,
) -> None:
    """A menu built with no variant must not print `# variant `."""
    notes = _export_notes(build_report(prime_menu, variant="", intent=""))
    assert "variant" not in notes and "intent" not in notes, notes


def test_the_parquet_keys_sort_into_the_order_the_notes_are_stated(
    report: object, tmp_path: Path
) -> None:
    """Parquet metadata is a mapping, and every reader sorts it.

    Until the `note_NN_` prefix, document order and alphabetical order agreed only
    because the two keys in play were `disclaimer` and `provenance_*`. Adding three
    facts whose names sort elsewhere broke the coincidence — which is the point of
    making the order a property of the key rather than of the word.
    """
    pl = pytest.importorskip("polars")
    raw = pl.read_parquet_metadata(report_to_parquet(report, tmp_path / "m.parquet"))
    ordered = [v for _, v in sorted((k, v) for k, v in raw.items() if k.startswith("note_"))]
    tsv = [line[2:] for line in report_to_tsv(report).splitlines() if line.startswith("# ")]
    assert ordered == tsv
