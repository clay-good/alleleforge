"""A resumed run writes a table of what *it* designed, and the table is the document.

Kill a cohort part way and resume it, and `--summary-tsv` holds only the items the second
run designed — the manifest is complete, the table is not. The counts line states the
arithmetic ("60 requested, 23 designed, 37 already done"), which is one `#` line among ten
above a table a colleague will open on its own. A 23-row file for a 60-patient cohort reads
as a 23-patient cohort, or as a 60-patient one that lost half its rows to failures, and the
`--summary-tsv` help said only "write a per-item TSV summary here".

Verified by interrupting a real run: 60 unique manifest records after a SIGTERM and a
resume, no duplicates and none missing — the manifest survives correctly, which is what
made the partial *table* the finding rather than a symptom of something worse.

The note reaches the terminal, the TSV, the Parquet and the API envelope through the one
function the other run-level notes use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.design.cohort_summary import cohort_headline_notes, cohort_rows, cohort_to_tsv
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


def _variants(fasta: Path) -> list[str]:
    return [f"chr11:{p}:{_base(fasta, p)}>{_ALT[_base(fasta, p)]}" for p in (1010, 1050, 1090)]


def _run(fasta: Path, manifest: Path, variants: list[str]) -> Any:
    return design_many(
        variants,
        reference=ReferenceGenome(fasta, build="hg38"),
        manifest_path=manifest,
        run_offtarget=False,
    )


def test_a_resumed_run_says_its_table_is_partial(fasta: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    variants = _variants(fasta)
    first = _run(fasta, manifest, variants[:1])
    assert first.total == 1

    second = _run(fasta, manifest, variants)
    counts = {
        "total": second.total,
        "succeeded": second.succeeded,
        "failed": second.failed,
        "skipped": second.skipped,
    }
    assert second.skipped == 1, second.skipped
    notes = cohort_headline_notes(cohort_rows(second), counts)
    partial = [n for n in notes if "not the whole cohort" in n]
    assert partial, notes
    assert "skipped as already recorded in the manifest" in partial[0]
    # The remedy, because a reader who wants one table has one.
    assert "--no-resume" in partial[0]


def test_a_run_that_skipped_nothing_says_nothing(fasta: Path, tmp_path: Path) -> None:
    """The half a one-sided test cannot see: the ordinary run must stay quiet."""
    manifest = tmp_path / "m.jsonl"
    report = _run(fasta, manifest, _variants(fasta))
    counts = {"total": report.total, "succeeded": report.succeeded, "failed": 0, "skipped": 0}
    assert not [
        n for n in cohort_headline_notes(cohort_rows(report), counts) if "whole cohort" in n
    ]


def test_the_note_reaches_the_written_table(fasta: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    variants = _variants(fasta)
    _run(fasta, manifest, variants[:1])
    second = _run(fasta, manifest, variants)
    counts = {
        "total": second.total,
        "succeeded": second.succeeded,
        "failed": second.failed,
        "skipped": second.skipped,
    }
    body = cohort_to_tsv(cohort_rows(second), second.provenance, counts=counts)
    assert "not the whole cohort" in body
    # ...and the table really is short, which is the fact the note is about.
    rows = [line for line in body.splitlines() if line and not line.startswith("#")]
    assert len(rows) - 1 == second.total < len(variants)


def test_the_help_no_longer_promises_the_cohort() -> None:
    """`--summary-tsv` said "a per-item TSV summary", with no hint that resume shortens it."""
    import typer

    from alleleforge.cli.main import app

    root = typer.main.get_command(app)
    option = next(
        p for p in root.commands["batch"].params if p.opts and p.opts[0] == "--summary-tsv"
    )
    assert "resumed run" in (option.help or "")
