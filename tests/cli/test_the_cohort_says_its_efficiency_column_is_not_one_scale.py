"""The surface built for sorting did not say what sorting it compares.

A cohort is triaged by sorting a column, and `best_efficiency` is the column people sort.
A real run puts these rows next to each other:

    chr2:1006:G>A   base_abe   0.6000
    chr2:1050:G>A   prime      0.3657
    chr2:1052:G>A   base_abe   0.6000

Sorting that column compares a base-editor number against a prime number — outputs of
different models, named in the provenance, neither calibrated against the other. The
single-variant menu states this in its rationale; the surface *designed* for sorting had
nothing, which is the wrong way round.

The sentence is one shared constant rather than two copies. Two wordings of one caveat
drift, and only one of them gets updated.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.design.ranking import CROSS_CHEMISTRY_NOTE


@pytest.fixture
def cohort(tmp_path: Path) -> tuple[Path, Path]:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return fasta, tmp_path


def _summary(fasta: Path, tmp_path: Path, variants: list[str], name: str) -> str:
    listing = tmp_path / f"{name}.txt"
    listing.write_text("\n".join(variants) + "\n")
    summary = tmp_path / f"{name}.tsv"
    result = CliRunner().invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(fasta),
            "--output-dir",
            str(tmp_path / f"{name}-out"),
            "--summary-tsv",
            str(summary),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return summary.read_text(encoding="utf-8")


def test_a_mixed_cohort_carries_the_note(cohort: tuple[Path, Path]) -> None:
    fasta, tmp_path = cohort
    text = _summary(fasta, tmp_path, ["chr2:1006:G>A", "chr2:1050:G>A"], "mixed")
    chemistries = {
        line.split("\t")[2]
        for line in text.splitlines()
        if not line.startswith("#") and "\t" in line
    } - {"best_chemistry", ""}
    assert len(chemistries) > 1, f"the fixture cohort is not mixed: {chemistries}"
    assert CROSS_CHEMISTRY_NOTE in text


def test_a_single_chemistry_cohort_does_not(cohort: tuple[Path, Path]) -> None:
    fasta, tmp_path = cohort
    text = _summary(fasta, tmp_path, ["chr2:1006:G>A", "chr2:1052:G>A"], "single")
    assert CROSS_CHEMISTRY_NOTE not in text


def test_the_note_is_one_constant_not_two_wordings() -> None:
    """The menu and the cohort say the same sentence, from the same place."""
    from alleleforge.cli import main as cli
    from alleleforge.design import ranking

    assert CROSS_CHEMISTRY_NOTE in ranking.CROSS_CHEMISTRY_NOTE
    assert "CROSS_CHEMISTRY_NOTE" in Path(cli.__file__).read_text(encoding="utf-8")


def test_the_note_survives_as_a_comment_line(cohort: tuple[Path, Path]) -> None:
    """It must be in the `#` block, so a comment-skipping reader still gets a clean table."""
    fasta, tmp_path = cohort
    text = _summary(fasta, tmp_path, ["chr2:1006:G>A", "chr2:1050:G>A"], "comment")
    carrier = [line for line in text.splitlines() if CROSS_CHEMISTRY_NOTE in line]
    assert carrier and all(line.startswith("#") for line in carrier)
