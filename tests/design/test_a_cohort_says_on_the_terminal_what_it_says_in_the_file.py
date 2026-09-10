"""The run-level notes lived only in a file this command does not write unless asked.

`aforge batch` without `--summary-tsv` prints a headline and one row per patient and writes
nothing. So a cohort screened against a population source built for another assembly said
nothing about it at all — not buried in a paragraph, *absent* — and the most common way to
run the command was the way that disclosed the least.

The split is between the note block's two halves. Provenance — the disclaimer, the version,
the build, the seed, the datasets, the clock — is unconditional and belongs in the artifact;
a terminal that has just shown the run does not need it repeated. The other half only
appears when something about the run is not what a reader would assume, and that is exactly
the half worth interrupting for.

The guard is the *rule*, not the instance: any note the block carries for a qualified run
and not for a clean one is conditional, and every conditional note must be one the terminal
gets. Written that way because the previous three rounds each elevated one member of a set
and left the rest.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.design.cohort_summary import (
    cohort_headline_notes,
    cohort_rows,
    cohort_to_tsv,
)
from alleleforge.genome.reference import ReferenceGenome

_ALT = {"A": "G", "G": "A", "C": "T", "T": "C"}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    random.seed(5)
    body = "".join(random.choice("ACGT") for _ in range(4000))
    body = body[:1000] + "ACCTGACTCCTGAGGAGAAG" + "TGG" + body[1023:]
    path = tmp_path / "ref.fa"
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


def _base(fasta: Path, one_based: int) -> str:
    import pyfaidx

    return str(pyfaidx.Fasta(str(fasta))["chr11"][one_based - 1 : one_based]).upper()


def _run(fasta: Path, tmp_path: Path, *, agreeing: bool) -> Any:
    from alleleforge.data.gnomad import GnomadDB

    rows = []
    for pos in (1100, 1200):
        base = _base(fasta, pos)
        ref, alt = (base, _ALT[base]) if agreeing else (_ALT[base], base)
        rows.append(f"chr11\t{pos}\t{ref}\t{alt}\t0.02\t0.055\t0.0008")
    sites = tmp_path / f"{'right' if agreeing else 'wrong'}.tsv"
    sites.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + "\n".join(rows) + "\n")
    variants = [f"chr11:{p}:{_base(fasta, p)}>{_ALT[_base(fasta, p)]}" for p in (1010, 1050)]
    return design_many(
        variants,
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(sites),
        populations=["afr", "nfe"],
    )


def test_a_wrong_build_source_reaches_the_terminal(fasta: Path, tmp_path: Path) -> None:
    notes = cohort_headline_notes(cohort_rows(_run(fasta, tmp_path, agreeing=False)))
    assert any("build mismatch, not an absence of population risk" in n for n in notes)


def test_a_clean_run_interrupts_with_nothing_it_need_not(fasta: Path, tmp_path: Path) -> None:
    notes = cohort_headline_notes(cohort_rows(_run(fasta, tmp_path, agreeing=True)))
    assert not [n for n in notes if "build mismatch" in n]


def test_every_conditional_note_in_the_file_reaches_the_terminal(
    fasta: Path, tmp_path: Path
) -> None:
    """The rule, derived: conditional means "absent from a clean run's block"."""
    qualified = _run(fasta, tmp_path, agreeing=False)
    clean = _run(fasta, tmp_path, agreeing=True)

    def block(report: Any) -> list[str]:
        # The run clock differs between any two runs and is provenance, not a note about
        # this run being unusual — the one line a set difference would mistake for one.
        return [
            re.sub(r"^started .*", "started <clock>", line.removeprefix("# "))
            for line in cohort_to_tsv(cohort_rows(report), report.provenance).splitlines()
            if line.startswith("#")
        ]

    conditional = set(block(qualified)) - set(block(clean))
    assert conditional, "the fixtures no longer differ, so this check is vacuous"
    elevated = set(cohort_headline_notes(cohort_rows(qualified)))
    missing = {n for n in conditional if n not in elevated}
    assert not missing, (
        f"these notes appear only when something is off and never reach the terminal: "
        f"{sorted(missing)}. Add them to `cohort_headline_notes`, or they are disclosed "
        "only to a run that asked for a file."
    )


def test_the_file_still_carries_them(fasta: Path, tmp_path: Path) -> None:
    """Elevating a note must not move it: the artifact is what a reader keeps."""
    report = _run(fasta, tmp_path, agreeing=False)
    body = cohort_to_tsv(cohort_rows(report), report.provenance)
    for note in cohort_headline_notes(cohort_rows(report)):
        assert note in body


def test_the_command_prints_them(fasta: Path, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    sites = tmp_path / "wrong.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\n"
        f"chr11\t1100\t{_ALT[_base(fasta, 1100)]}\t{_base(fasta, 1100)}\t0.02\t0.05\n"
    )
    cohort = tmp_path / "cohort.txt"
    cohort.write_text(f"chr11:1010:{_base(fasta, 1010)}>{_ALT[_base(fasta, 1010)]}\n")
    result = CliRunner().invoke(
        app,
        [
            "batch",
            str(cohort),
            "--reference-fasta",
            str(fasta),
            "--populations",
            "afr",
            "--gnomad",
            str(sites),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert "build mismatch" in result.stderr, result.stderr
    # ...on stderr, so the row table on stdout stays a table.
    assert "build mismatch" not in result.stdout
