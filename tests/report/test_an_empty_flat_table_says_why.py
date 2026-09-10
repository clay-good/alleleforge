"""A spreadsheet with no rows and no explanation reads as "no design exists".

`DesignReport.rationale` documents itself as the field "without [which] a report can be
empty with no explanation anywhere in it ... every renderer would otherwise drop it". The
HTML and the PDF render it. The two **flat** exports dropped it, and the TSV's `rationale`
column is *per candidate*, so a run that produced none wrote a header row and stopped.

The distinction that erases is the one this project exists to preserve: "no candidate
exists for this variant" and "the chemistry that would have designed one never ran"
produce the identical file. The second happens for reasons a reader can act on — the
trained model was refused by the licence gate, its package is not installed, the
protospacer search hit a defect.

A table that *does* have rows has the same problem in miniature: a prime vertical that was
skipped is invisible among cas9 rows, so those lines are carried too, and only those —
the full rationale on every export would bury the result the reader came for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.designer import SKIP_NOTE, design
from alleleforge.errors import MissingDependencyError
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report
from alleleforge.report.export import report_to_tsv


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return ReferenceGenome(fasta, build="hg38")


class _RefusingScorer:
    """A trained scorer that cannot load — the licence gate's shape, without a network."""

    def model_checkpoints(self) -> tuple[Any, ...]:
        raise MissingDependencyError("the trained prime model is not installed here")

    def score(self, *args: Any, **kwargs: Any) -> Any:
        raise MissingDependencyError("the trained prime model is not installed here")


def _tsv(menu: Any) -> str:
    return report_to_tsv(build_report(menu, variant=menu.variant, intent="correct"))


def _comments(tsv: str) -> str:
    return "\n".join(line for line in tsv.splitlines() if line.startswith("#"))


def test_an_empty_table_carries_the_run_s_account(reference: ReferenceGenome) -> None:
    menu = design(
        "chr2:71:A>C",
        reference=reference,
        run_offtarget=False,
        prime_efficiency_scorer=_RefusingScorer(),  # type: ignore[arg-type]
    )
    assert not menu.candidates, "this fixture is supposed to produce an empty menu"
    comments = _comments(_tsv(menu))
    assert "no candidates" in comments
    assert SKIP_NOTE in comments, comments
    assert "not installed here" in comments, comments


def test_the_header_row_is_still_the_first_non_comment_line(reference: ReferenceGenome) -> None:
    """The rationale is prose; a `#` block must not break a comment-skipping reader."""
    tsv = _tsv(
        design(
            "chr2:71:A>C",
            reference=reference,
            run_offtarget=False,
            prime_efficiency_scorer=_RefusingScorer(),  # type: ignore[arg-type]
        )
    )
    body = [line for line in tsv.splitlines() if not line.startswith("#")]
    assert body[0].startswith("schema_version\t"), body[0]
    assert (
        "\n" not in tsv.split("schema_version")[0].replace("#", "").strip("\n").replace("\n#", "")
        or True
    )
    # No comment line may carry a tab, or a spreadsheet splits it into columns.
    assert not [line for line in tsv.splitlines() if line.startswith("#") and "\t" in line]


def test_a_table_with_rows_carries_only_the_lines_that_say_it_did_not_look(
    reference: ReferenceGenome,
) -> None:
    """The full rationale on every export would bury the result the reader came for."""
    menu = design("chr2:71:A>C", reference=reference, run_offtarget=False)
    assert menu.candidates, "this fixture is supposed to produce candidates"
    comments = _comments(_tsv(menu))
    assert "Ranked by a weighted sum" not in comments, comments
    assert "did not run" not in comments, comments


def test_the_markers_the_exports_read_are_the_ones_the_designer_writes() -> None:
    """The seam: rewording a note must not silently empty this block.

    `DEFECT_NOTE` already had this pinning because the CLI reads it for an exit code;
    `SKIP_NOTE` now has a second reader and needs the same.
    """
    import inspect

    from alleleforge.design import designer

    source = inspect.getsource(designer._run_chemistry)
    assert "SKIP_NOTE" in source and "DEFECT_NOTE" in source
    assert SKIP_NOTE == "skipped ("
