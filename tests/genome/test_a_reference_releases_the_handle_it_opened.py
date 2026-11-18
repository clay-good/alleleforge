"""A `ReferenceGenome` promises to close its FASTA, and nothing checked that it does.

A statement-deletion sweep removed three statements from `genome/reference.py` one at a
time and the whole suite stayed green for each:

* ``self._fasta.close()`` — the entire body of :meth:`close`, whose docstring reads
  *"Close the underlying FASTA handle"*;
* ``self.close()`` — the entire body of :meth:`__exit__`, so ``with
  ReferenceGenome(...) as ref:`` would leave the handle open on the way out;
* ``root.mkdir(parents=True, exist_ok=True)`` before a consented download, without
  which the fetch writes into a directory that does not exist.

None of them changes an answer. A reference that never closes returns exactly the same
bases, and a suite that reads bases cannot tell the difference — which is why a cohort
run could open the genome once per item for as long as it did (Round 668) with every
result correct. The handle count is the observable here, so the handle count is what
this file asserts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import BuildDescriptor, ReferenceGenome

_SEQ = "ACGTACGTACGTACGTACGT" * 10


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.fa"
    path.write_text(">chr1\n" + _SEQ + "\n")
    return path


def _is_closed(reference: ReferenceGenome) -> bool:
    """Whether the pyfaidx handle underneath has actually been released."""
    handle = getattr(reference._fasta, "faidx", None)
    stream = getattr(handle, "file", None) if handle is not None else None
    if stream is None:  # pragma: no cover - a pyfaidx layout we do not know
        pytest.skip("cannot see the underlying file object on this pyfaidx")
    return bool(stream.closed)


def test_the_handle_is_open_while_the_reference_is(fasta: Path) -> None:
    """The premise: without an open handle to start with, nothing below is a check."""
    reference = ReferenceGenome(fasta, build="hg38")
    assert not _is_closed(reference)
    reference.close()


def test_close_closes_the_fasta(fasta: Path) -> None:
    reference = ReferenceGenome(fasta, build="hg38")
    reference.close()
    assert _is_closed(reference)


def test_leaving_the_context_closes_the_fasta(fasta: Path) -> None:
    """`__exit__` is the half a caller never calls by hand."""
    with ReferenceGenome(fasta, build="hg38") as reference:
        assert not _is_closed(reference)
    assert _is_closed(reference)


def test_a_consented_download_creates_the_cache_directory(tmp_path: Path) -> None:
    """The fetch writes into a directory `from_build` is responsible for making."""
    import hashlib

    payload = ">chr1\n" + _SEQ + "\n"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    descriptor = BuildDescriptor(
        name="probe",
        version="v1",
        source_url="https://example.invalid/probe.fa",
        citation="none",
        sha256=digest,
    )
    root = tmp_path / "not" / "yet" / "there"
    assert not root.exists()

    def downloader(url: str, dest: Path) -> None:
        dest.write_text(payload)

    reference = ReferenceGenome.from_build(
        "probe", cache_dir=root, consent=True, downloader=downloader, descriptor=descriptor
    )
    assert root.is_dir()
    reference.close()
