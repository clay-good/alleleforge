"""A population off-target's frequency is the number that makes it a decision.

Found by running the real command. `aforge offtarget --gnomad` reproduces the
rs114518452-style reference-bias case — a spacer with no PAM in the reference and an
AFR-enriched allele that creates one — and the human render said:

    chr2:10-30(+)  pam=CGG  mm=0  score=1.0  mit=1.0  population chr2:32:T>G

`score=1.0` looks catastrophic and is the same string whether the causal allele is in one
genome in ten or one in a thousand. Those are different decisions. The JSON had carried
`frequency` and the per-ancestry breakdown from the start, and the HTML and PDF renders
have shown the per-ancestry worst case since it existed — so a CLI user of the feature
this project exists to provide had to re-run with `--json` to find out whether the site
mattered, and the surfaces disagreed about what a reader is told.

The row now ends `carried at 0.105 (afr 0.105, nfe 0.001)` — a hundredfold difference
between two ancestries at one site — and the summary carries the per-ancestry worst case.
A reference-only scan prints neither.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bias_case(tmp_path: Path) -> tuple[Path, Path, str]:
    """The reference-bias case as CLI inputs (mirrors the fixture in test_cli.py)."""
    spacer = "GACCATGCAACCTTGAACGT"
    pad = "T" * 10
    fasta = tmp_path / "bias.fa"
    fasta.write_text(f">chr2\n{pad}{spacer}CGT{pad}\n")
    sites = tmp_path / "bias.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\tamr\teas\tnfe\tsas\n"
        "chr2\t33\tT\tG\t0.03\t0.105\t0.012\t0.0\t0.001\t0.0\n"
    )
    return fasta, sites, spacer


def _run(runner: CliRunner, args: list[str]) -> str:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output + result.stderr
    return result.output


def test_the_row_states_how_common_the_causal_allele_is(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    fasta, sites, spacer = bias_case
    output = _run(
        runner,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--gnomad",
            str(sites),
            "--populations",
            "afr,nfe",
        ],
    )
    assert "carried at 0.105" in output
    assert "afr 0.105" in output and "nfe 0.001" in output


def test_the_summary_carries_the_per_ancestry_worst_case(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """The HTML and PDF show this; the CLI put it in the JSON only."""
    fasta, sites, spacer = bias_case
    output = _run(
        runner,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--gnomad",
            str(sites),
            "--populations",
            "afr,nfe",
        ],
    )
    assert "worst off-target score by ancestry:" in output
    assert "afr 1.000" in output


def test_a_reference_only_scan_says_neither(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """Nothing to weight and nothing to stratify: silence, not a zero."""
    fasta, _sites, spacer = bias_case
    output = _run(runner, ["offtarget", spacer, "--reference-fasta", str(fasta)])
    assert "carried at" not in output
    assert "by ancestry" not in output
    assert "expected burden" not in output


def test_the_human_render_agrees_with_the_json(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """Same run, two forms: the number a person reads is the number a machine reads."""
    fasta, sites, spacer = bias_case
    args = [
        "offtarget",
        spacer,
        "--reference-fasta",
        str(fasta),
        "--gnomad",
        str(sites),
        "--populations",
        "afr,nfe",
    ]
    human = _run(runner, args)
    payload = json.loads(_run(runner, [*args, "--json"]))
    site = payload["sites"][0]
    assert f"carried at {site['frequency']:.3g}" in human
    for ancestry, value in site["ancestries"].items():
        assert f"{ancestry} {value:.3g}" in human
    assert f"{payload['expected_burden']:.3f}" in human
