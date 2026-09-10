"""A gnomAD file for the wrong build contributed nothing and said nothing.

The enumerator has always done the right thing with a record whose asserted REF is not the
base this genome has::

    if ref_seq[rel : rel + len(ref)].upper() != ref.upper():
        return []  # the variant's ref does not match this build; skip safely

Applying an ALT to a base the genome does not have builds a haplotype nobody carries, so
skipping is correct. Skipping *silently* is not. `sources_considered` counts records **found
in the region**, which a whole file for the wrong build satisfies, so the report's own
"supplied but contributing nothing in this region" sentence — written for exactly this
class of failure — could not fire. A wrong-build population file produced a report
identical to one whose file was fine and simply had nothing to add: same specificity, same
empty ancestry breakdown, same reassuring silence.

That is this project's headline defect class — a real safety input inert on its consumed
axis with everything green — inside the machinery built to prevent it. The patient-VCF path
refuses the same mistake loudly at load, but only on the CLI and only for variants it
resolves; a caller handing `design()` a list of `Variant` reaches the same skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

_SPACER = "ACCTGACTCCTGAGGAGAAG"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    """A contig with the on-target site and one 1-mismatch off-target."""
    import random

    random.seed(11)
    seq = list("".join(random.choice("ACGT") for _ in range(6000)))
    seq[2000:2023] = list(_SPACER + "TGG")
    near = list(_SPACER)
    near[11] = "A"
    seq[3000:3023] = near + list("AGG")
    path = tmp_path / "ref.fa"
    body = "".join(seq)
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


@pytest.fixture
def genome(fasta: Path) -> ReferenceGenome:
    return ReferenceGenome(fasta, build="hg38")


def _gnomad(tmp_path: Path, rows: str, name: str) -> GnomadDB:
    path = tmp_path / name
    path.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + rows)
    return GnomadDB.from_sites_tsv(path)


def _base_at(fasta: Path, one_based: int) -> str:
    """The reference base a 1-based gnomAD position names."""
    import pyfaidx

    return str(pyfaidx.Fasta(str(fasta))["chr11"][one_based - 1 : one_based]).upper()


def test_a_file_for_the_wrong_build_is_named_as_one(
    genome: ReferenceGenome, fasta: Path, tmp_path: Path
) -> None:
    wrong = {"A": "C", "C": "G", "G": "T", "T": "A"}
    rows = "".join(
        f"chr11\t{pos}\t{wrong[_base_at(fasta, pos)]}\tA\t0.02\t0.055\t0.0008\n"
        for pos in (3005, 3010)
    )
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=genome,
        gnomad=_gnomad(tmp_path, rows, "wrong.tsv"),
        populations=["afr", "nfe"],
    )
    assert report.source_build_mismatch == {"gnomad": 2}
    description = report.search_description()
    assert "build mismatch" in description
    assert "every one of the 2" in description
    # And it says what the silence used to mean.
    assert "not an absence of population risk" in description


def test_one_stale_record_reads_differently_from_a_wrong_file(
    genome: ReferenceGenome, fasta: Path, tmp_path: Path
) -> None:
    """A file with one bad row is a stale record; a file with only bad rows is a build."""
    wrong = {"A": "C", "C": "G", "G": "T", "T": "A"}
    rows = (
        f"chr11\t3005\t{_base_at(fasta, 3005)}\tA\t0.02\t0.055\t0.0008\n"
        f"chr11\t3010\t{wrong[_base_at(fasta, 3010)]}\tA\t0.02\t0.055\t0.0008\n"
    )
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=genome,
        gnomad=_gnomad(tmp_path, rows, "mixed.tsv"),
        populations=["afr", "nfe"],
    )
    assert report.source_build_mismatch == {"gnomad": 1}
    description = report.search_description()
    assert "1 of the 2" in description


def test_a_file_that_agrees_with_the_reference_says_nothing(
    genome: ReferenceGenome, fasta: Path, tmp_path: Path
) -> None:
    """The half a refusal-only test cannot see: a correct file must stay quiet."""
    rows = "".join(
        f"chr11\t{pos}\t{_base_at(fasta, pos)}\tA\t0.02\t0.055\t0.0008\n" for pos in (3005, 3010)
    )
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=genome,
        gnomad=_gnomad(tmp_path, rows, "right.tsv"),
        populations=["afr", "nfe"],
    )
    assert report.source_build_mismatch == {}
    assert "build mismatch" not in report.search_description()
