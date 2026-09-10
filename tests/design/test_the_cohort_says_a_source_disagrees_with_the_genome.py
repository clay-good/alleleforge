"""The cohort table is where a wrong-build population file costs most, and said nothing.

The single-variant surfaces learned to name a source whose records assert a base this
genome does not have. The cohort table did not, and it is the document for the runs where
the mistake is expensive: `offtarget_sources` reads `gnomad=47` on every one of five
hundred rows whether the file was right or built against another assembly, and nobody opens
five hundred per-variant reports to find out which.

Two disclosures, because two readers: a key in the same mapping for whatever parses the
table, and one line in the note block for the person who scans it — a constant repeated in
five hundred cells is not something anyone notices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.design.cohort_summary import cohort_rows, cohort_to_tsv
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


def _gnomad(fasta: Path, tmp_path: Path, *, agreeing: bool) -> Any:
    from alleleforge.data.gnomad import GnomadDB

    rows = []
    for pos in (1100, 1200):
        base = _base(fasta, pos)
        ref, alt = (base, _ALT[base]) if agreeing else (_ALT[base], base)
        rows.append(f"chr11\t{pos}\t{ref}\t{alt}\t0.02\t0.055\t0.0008")
    path = tmp_path / ("right.tsv" if agreeing else "wrong.tsv")
    path.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + "\n".join(rows) + "\n")
    return GnomadDB.from_sites_tsv(path)


def _run(fasta: Path, tmp_path: Path, *, agreeing: bool) -> Any:
    reference = ReferenceGenome(fasta, build="hg38")
    variants = [f"chr11:{p}:{_base(fasta, p)}>{_ALT[_base(fasta, p)]}" for p in (1010, 1050)]
    return design_many(
        variants,
        reference=reference,
        gnomad=_gnomad(fasta, tmp_path, agreeing=agreeing),
        populations=["afr", "nfe"],
    )


def test_a_row_says_which_records_were_unusable(fasta: Path, tmp_path: Path) -> None:
    rows = cohort_rows(_run(fasta, tmp_path, agreeing=False))
    sources = [r["offtarget_sources"] for r in rows if r["status"] == "ok"]
    assert sources, "no item designed, so the assertion below would be vacuous"
    for entry in sources:
        assert entry["gnomad:build-mismatch"] == 2
        # The considered count stays: "2 found, 2 unusable" is the whole statement.
        assert entry["gnomad"] == 2


def test_the_note_block_says_it_once(fasta: Path, tmp_path: Path) -> None:
    report = _run(fasta, tmp_path, agreeing=False)
    notes = [
        line
        for line in cohort_to_tsv(cohort_rows(report), report.provenance).splitlines()
        if line.startswith("#")
    ]
    disagreed = [n for n in notes if "disagreed with this reference" in n]
    assert len(disagreed) == 1, notes
    assert "not an absence of population risk" in disagreed[0]


def test_a_file_that_agrees_qualifies_nothing(fasta: Path, tmp_path: Path) -> None:
    """The half a one-sided test cannot see."""
    report = _run(fasta, tmp_path, agreeing=True)
    rows = cohort_rows(report)
    for entry in (r["offtarget_sources"] for r in rows if r["status"] == "ok"):
        assert "gnomad:build-mismatch" not in entry
    body = cohort_to_tsv(rows, report.provenance)
    assert "disagreed with this reference" not in body
