"""A mixed-matrix report sorted rows by score and would not say which scale each used.

The published CFD matrix is defined for a 20-nt ungapped alignment, so a bulge-collapsed
or off-length hit falls back to a length-relative approximation — per hit. One report can
therefore hold two scales at once, and a real bulged scan does:

    matrices in report: ['doench-2016-cfd', 'doench-2016-seed-tolerance-approximation']

`effective_matrix()` reports both, joined, so a reader knows two scales were used. It
cannot say *which row is which* — and the rows are printed in score order, so a published
`0.50` and an approximated `0.60` sit adjacent with nothing to tell them apart. The JSON
has carried `score_matrix` per site from the start; the human form had not, which is the
same machine-readable-only gap this session keeps finding.

Only when the report is genuinely mixed. A homogeneous table already names its one matrix
on the header line, and repeating it on every row is noise.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app


def _mutate(spacer: str, k: int, seed: int) -> str:
    rng = random.Random(seed)
    bases = list(spacer)
    for position in rng.sample(range(len(bases)), k):
        bases[position] = rng.choice([b for b in "ACGT" if b != bases[position]])
    return "".join(bases)


@pytest.fixture
def bulged_case(tmp_path: Path) -> tuple[Path, str]:
    """A reference whose hits include bulged alignments, which fall back per site."""
    rng = random.Random(5)
    spacer = "".join(rng.choice("ACGT") for _ in range(20))
    pad = lambda n: "".join(rng.choice("ACGT") for _ in range(n))  # noqa: E731
    parts = [pad(200), spacer, "AGG", pad(200)]
    for k in (1, 2):
        parts += [_mutate(spacer, k, k), "TGG", pad(150)]
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "".join(parts) + "\n")
    return fasta, spacer


def _run(fasta: Path, spacer: str, *extra: str) -> str:
    result = CliRunner().invoke(
        app,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--cfd-threshold",
            "0.0",
            "--mit-threshold",
            "0.0",
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return result.output


def test_a_mixed_report_labels_every_row(bulged_case: tuple[Path, str]) -> None:
    fasta, spacer = bulged_case
    output = _run(fasta, spacer, "--dna-bulges", "1", "--rna-bulges", "1")
    payload = json.loads(
        CliRunner()
        .invoke(
            app,
            [
                "offtarget",
                spacer,
                "--reference-fasta",
                str(fasta),
                "--dna-bulges",
                "1",
                "--rna-bulges",
                "1",
                "--cfd-threshold",
                "0.0",
                "--mit-threshold",
                "0.0",
                "--json",
            ],
        )
        .stdout
    )
    matrices = {s["score_matrix"] for s in payload["sites"] if s["score_matrix"]}
    assert len(matrices) > 1, f"the fixture is not mixed: {matrices}"
    for matrix in matrices:
        assert f"matrix={matrix}" in output, f"no row is labelled {matrix}"


def test_a_single_matrix_report_stays_clean(bulged_case: tuple[Path, str]) -> None:
    """The header names the one matrix; repeating it per row would be noise."""
    fasta, spacer = bulged_case
    output = _run(fasta, spacer, "--dna-bulges", "0", "--rna-bulges", "0")
    assert "matrix=" not in output


def test_the_header_still_reconciles_both(bulged_case: tuple[Path, str]) -> None:
    """Row labels complement the report-level statement rather than replacing it."""
    fasta, spacer = bulged_case
    output = _run(fasta, spacer, "--dna-bulges", "1", "--rna-bulges", "1")
    assert "effective" in output


def test_a_bulged_row_does_not_read_as_a_perfect_match(bulged_case: tuple[Path, str]) -> None:
    """`mm=0` is the most reassuring thing a row can say, and a bulged hit says it.

    Three of the five rows in this scan are `mm=0` alignments through a gap — 21-nt and
    19-nt intervals, not 20-nt matches. Only the interval width gave that away, and no
    reader computes it. The bulge counts are shown when non-zero, which is also what
    explains the fallback matrix beside them.
    """
    fasta, spacer = bulged_case
    output = _run(fasta, spacer, "--dna-bulges", "1", "--rna-bulges", "1")
    bulged_rows = [line for line in output.splitlines() if "dna=1" in line or "rna=1" in line]
    assert bulged_rows, "the fixture produced no bulged alignment"
    for row in bulged_rows:
        assert "mm=" in row, row
    # Every bulged row is one the published matrix could not score.
    for row in bulged_rows:
        assert "approximation" in row, f"a bulged row was scored by the published matrix: {row}"


def test_an_ungapped_row_says_nothing_about_bulges(bulged_case: tuple[Path, str]) -> None:
    fasta, spacer = bulged_case
    output = _run(fasta, spacer, "--dna-bulges", "0", "--rna-bulges", "0")
    assert "dna=" not in output and "rna=" not in output
