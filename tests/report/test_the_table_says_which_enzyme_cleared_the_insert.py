"""An empty hazard cell is a claim about one enzyme. The table must name it.

`oligo_warnings` carries the ordering hazard a pipeline filters on before placing a DNA
order: an internal Type IIS site means the cloning enzyme cuts the insert. It became
interpretable only against a fact the table did not carry the moment the cloning vector
became the caller's to choose — an empty cell means "clean for **this** enzyme", and
`px330-bbsi` and `lentiguide-bsmbi` clear different sequences.

Worse than a global setting: one report can mix them. An sgRNA-only vector cannot receive
a pegRNA 3' extension, so selecting one leaves pegRNA candidates on the pegRNA acceptor —
a single table with BbsI-screened rows and BsaI-screened rows in it. That is the
`offtarget_worst_matrix` situation exactly, and it was solved there by naming the matrix
per row.

The human renders name the scheme on every candidate's block. The flat table did not.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import build_report
from alleleforge.report.export import TSV_COLUMNS, report_to_tsv
from alleleforge.report.oligos import PX330_BBSI
from alleleforge.types.edit import EditIntent

_BBSI_SPACER = "ACCTGAAGACTTACGCATAC"


def _rows(report: object) -> list[dict[str, str]]:
    lines = [line for line in report_to_tsv(report).splitlines() if not line.startswith("#")]
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]


@pytest.fixture
def nuclease_menu(tmp_path: Path) -> object:
    rng = random.Random(7)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[1000:1023] = list(_BBSI_SPACER + "TGG")
    fasta = tmp_path / "bbsi.fa"
    fasta.write_text(">chr1\n" + "".join(seq) + "\n")
    return design(
        f"chr1:1018:{_BBSI_SPACER[17]}>A",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
        intent=EditIntent.KNOCK_OUT,
    )


def test_the_columns_exist_in_the_schema() -> None:
    assert "oligo_scheme" in TSV_COLUMNS
    assert "oligo_enzyme" in TSV_COLUMNS


def test_a_clean_row_names_the_enzyme_that_cleared_it(nuclease_menu: object) -> None:
    """The defect: `oligo_warnings = ""` with nothing saying what looked."""
    rows = _rows(build_report(nuclease_menu, with_oligos=True))
    clean = [r for r in rows if r["oligo_warnings"] == ""]
    assert clean, "no clean row — this check would be vacuous"
    for row in clean:
        assert row["oligo_scheme"] == "lentiguide-bsmbi", row
        assert row["oligo_enzyme"] == "BsmBI", row


def test_the_columns_follow_the_chosen_vector(nuclease_menu: object) -> None:
    rows = _rows(build_report(nuclease_menu, with_oligos=True, scheme=PX330_BBSI))
    flagged = [r for r in rows if r["oligo_warnings"]]
    assert flagged, "the pX330 screen found nothing in an insert carrying GAAGAC"
    for row in flagged:
        assert row["oligo_scheme"] == "px330-bbsi"
        assert row["oligo_enzyme"] == "BbsI"
        assert "internal-BbsI-site" in row["oligo_warnings"]


def test_a_table_that_mixes_enzymes_says_so_per_row(tmp_path: Path) -> None:
    """One vector choice, two enzymes in one table — the reason this is per-row."""
    rng = random.Random(7)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[1000:1023] = list(_BBSI_SPACER + "TGG")
    fasta = tmp_path / "mixed.fa"
    fasta.write_text(">chr1\n" + "".join(seq) + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    variant = f"chr1:1018:{_BBSI_SPACER[17]}>A"

    nuclease = _rows(
        build_report(
            design(variant, reference=reference, run_offtarget=False, intent=EditIntent.KNOCK_OUT),
            with_oligos=True,
            scheme=PX330_BBSI,
        )
    )
    prime = _rows(
        build_report(
            design(variant, reference=reference, run_offtarget=False),
            with_oligos=True,
            scheme=PX330_BBSI,
        )
    )
    # The same requested vector, two acceptors, because a pegRNA extension cannot go
    # into an sgRNA vector. Each row states which one screened it.
    assert {r["oligo_enzyme"] for r in nuclease} == {"BbsI"}
    assert {r["oligo_enzyme"] for r in prime} == {"BsaI"}


def test_no_oligos_leaves_both_columns_empty(nuclease_menu: object) -> None:
    """No screen ran, so no enzyme cleared anything — not a reassuring default."""
    for row in _rows(build_report(nuclease_menu, with_oligos=False)):
        assert row["oligo_scheme"] == ""
        assert row["oligo_enzyme"] == ""
        assert row["oligo_warnings"] == ""
