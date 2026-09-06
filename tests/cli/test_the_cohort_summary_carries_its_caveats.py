"""The cohort summary TSV must carry the caveats the per-design TSV does.

`aforge batch --summary-tsv` writes the file a whole-cohort run is read through: one
row per variant, with efficiencies, specificities and off-target counts. It carried
none of the five whole-document facts:

    not a medical device     sum.tsv:.  item.json:.
    0-based                  sum.tsv:.  item.json:Y
    reference identity       sum.tsv:.  item.json:.
    hg38                     sum.tsv:.  item.json:Y
    seed                     sum.tsv:.  item.json:Y

The previous round gave the *per-design* TSV a leading `#` note block and did not
reach this one, which is the same drift the fact-by-surface table was written to stop —
the table covered the four renders of a `DesignReport` and a cohort summary is not one
of them. It is also the higher-stakes file: a cohort summary is what gets forwarded,
and a row per patient with a bare `best_specificity` and no statement of which genome
was searched is not interpretable.

The notes lead the file as `#` comments, as in the per-design export, so the column
header remains the first non-comment line.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cohort(tmp_path: Path) -> tuple[Path, Path]:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    inputs = tmp_path / "cohort.txt"
    inputs.write_text("chr2:71:A>C\nchr2:71:A>T\n")
    return fasta, inputs


def _summary(runner: CliRunner, cohort: tuple[Path, Path], tmp_path: Path) -> str:
    fasta, inputs = cohort
    out = tmp_path / "sum.tsv"
    result = runner.invoke(
        app,
        [
            "batch",
            str(inputs),
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "1",
            "--summary-tsv",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return out.read_text()


def test_the_table_is_unchanged_for_a_comment_aware_reader(
    runner: CliRunner, cohort: tuple[Path, Path], tmp_path: Path
) -> None:
    text = _summary(runner, cohort, tmp_path)
    comments = [line for line in text.splitlines() if line.startswith("#")]
    data = [line for line in text.splitlines() if not line.startswith("#")]
    assert comments, "no notes were emitted"
    assert data[0].startswith("item_id\tstatus\t")
    assert len(data) == 3  # header + two items
    widths = {len(line.split("\t")) for line in data}
    assert len(widths) == 1, widths


@pytest.mark.parametrize(
    "fact, needle",
    [
        ("research-use disclaimer", "not a medical device"),
        ("coordinate convention", "0-based"),
        ("reference identity", "pins contig names"),
        ("reference build", "hg38"),
        ("seed", "20240501"),
    ],
)
def test_the_summary_states_the_fact(
    runner: CliRunner, cohort: tuple[Path, Path], tmp_path: Path, fact: str, needle: str
) -> None:
    notes = " ".join(
        line for line in _summary(runner, cohort, tmp_path).splitlines() if line.startswith("#")
    )
    assert needle in notes, f"the cohort summary omits the {fact}"


def test_the_parallel_path_says_why_it_has_no_run_wide_reference(
    runner: CliRunner, cohort: tuple[Path, Path], tmp_path: Path
) -> None:
    """`reference build None` would read as a missing value, not a located one."""
    fasta, inputs = cohort
    out = tmp_path / "par.tsv"
    result = runner.invoke(
        app,
        [
            "batch",
            str(inputs),
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-workers",
            "2",
            "--summary-tsv",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    notes = " ".join(ln for ln in out.read_text().splitlines() if ln.startswith("#"))
    assert "reference build None" not in notes
    assert "not recorded run-wide" in notes
    assert "each item's own result records the genome it used" in notes
