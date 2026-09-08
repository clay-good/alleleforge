"""A `.fai` that does not belong to the FASTA must not be read through.

The index is not re-derived on open — `rebuild=False`, so a read-only reference
mount works — so when the FASTA is replaced or truncated after indexing (writing a
different assembly to the same path is the ordinary way this happens) pyfaidx warns
about mtimes and then reads the stale offsets anyway. A library caller, an HTTP
deployment and a served page never see a Python warning.

What they get instead is not a failure. Before this check, against a FASTA holding
only `chr1`, with an index from a two-contig file:

    contigs()               -> ('chr1', 'chr2')
    contig_length('chr2')   -> 40
    fetch_result(chr2:0-20) -> '' with padded=False

"I read those twenty bases, and they are nothing" is the one answer this project
must never give: an unpadded empty sequence flows into design and off-target
scoring as measured data.

A single `stat` against the offsets the index itself asserts settles it, with no
false positives — a file shorter than the bytes the index requires cannot be the
file it describes, whatever the mtimes say. A *longer* file is left alone: an
appended contig does not move the ones already indexed.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from alleleforge.errors import ReferenceIndexError
from alleleforge.genome.reference import ReferenceGenome

_TWO_CONTIGS = ">chr1\n" + "ACGT" * 15 + "\n>chr2\n" + "TTTT" * 10 + "\n"


def _indexed(tmp_path: Path, text: str) -> Path:
    """Write a FASTA and build its index by opening it once."""
    fasta = tmp_path / "ref.fa"
    fasta.write_text(text, encoding="utf-8")
    ReferenceGenome(fasta, build="hg38")
    assert fasta.with_name("ref.fa.fai").exists()
    return fasta


def _open_ignoring_the_mtime_warning(fasta: Path) -> ReferenceGenome:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return ReferenceGenome(fasta, build="hg38")


def test_the_fixture_really_is_indexed(tmp_path: Path) -> None:
    """Vacuity floor: the good case opens and reads."""
    fasta = _indexed(tmp_path, _TWO_CONTIGS)
    reference = _open_ignoring_the_mtime_warning(fasta)
    assert reference.contigs == ("chr1", "chr2")
    assert reference.contig_length("chr2") == 40


def test_a_shorter_fasta_than_the_index_describes_is_refused(tmp_path: Path) -> None:
    fasta = _indexed(tmp_path, _TWO_CONTIGS)
    fasta.write_text(">chr1\n" + "AAAA" * 5 + "\n", encoding="utf-8")  # chr2 is gone
    with pytest.raises(ReferenceIndexError) as excinfo:
        _open_ignoring_the_mtime_warning(fasta)
    message = str(excinfo.value)
    assert "samtools faidx" in message, message
    assert "does not belong to this FASTA" in message, message


def test_an_appended_contig_is_not_refused(tmp_path: Path) -> None:
    """A longer file does not move the offsets already indexed."""
    fasta = _indexed(tmp_path, _TWO_CONTIGS)
    fasta.write_text(_TWO_CONTIGS + ">chr3\n" + "GGGG" * 5 + "\n", encoding="utf-8")
    reference = _open_ignoring_the_mtime_warning(fasta)
    assert reference.contigs == ("chr1", "chr2")


def test_a_rewritten_identical_fasta_is_not_refused(tmp_path: Path) -> None:
    """Rewriting the same bytes changes the mtime and nothing else."""
    fasta = _indexed(tmp_path, _TWO_CONTIGS)
    fasta.write_text(_TWO_CONTIGS, encoding="utf-8")
    assert _open_ignoring_the_mtime_warning(fasta).contig_length("chr2") == 40


def test_a_fasta_with_no_trailing_newline_is_not_refused(tmp_path: Path) -> None:
    """The check must not require the final line terminator a FASTA may omit."""
    fasta = _indexed(tmp_path, _TWO_CONTIGS)
    fasta.write_text(_TWO_CONTIGS.rstrip("\n"), encoding="utf-8")
    assert _open_ignoring_the_mtime_warning(fasta).contig_length("chr2") == 40
