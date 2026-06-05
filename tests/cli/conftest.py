"""Fixtures for the Phase 12 CLI tests (require the optional ``cli`` extra)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402


@pytest.fixture
def runner() -> CliRunner:
    """Return a Typer/click test runner (stdout and stderr captured separately)."""
    return CliRunner()


@pytest.fixture
def prime_fasta(tmp_path: Path) -> Path:
    """A FASTA whose locus yields prime (pegRNA) candidates for chr2:71:A>C."""
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")  # plus pegRNA PAM
    seq[55:58] = list("CCA")  # minus ngRNA PAM (PE3b)
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return fasta


@pytest.fixture
def nuclease_fasta(tmp_path: Path) -> Path:
    """A FASTA yielding SpCas9 nuclease candidates for chr2:26 knock-out."""
    pad = "T" * 20
    fasta = tmp_path / "nuc.fa"
    fasta.write_text(">chr2\n" + pad + "ACGTAACGTTACGTAACGTT" + "TGG" + pad + "\n")
    return fasta


@pytest.fixture
def cohort_fasta(tmp_path: Path) -> Path:
    """A FASTA whose chr2:26 locus is ABE-installable (A>G) for cohort runs."""
    pad = "T" * 20
    contig = pad + "TTTAAACGTTTTTTTTTTTT" + "TGG" + pad  # in-window A at chr2:26, NGG PAM
    fasta = tmp_path / "cohort.fa"
    fasta.write_text(">chr2\n" + contig + "\n")
    return fasta


@pytest.fixture
def design_cmd() -> Callable[[Path, str], list[str]]:
    """Return a helper building a ``design`` argv for a prime install case."""

    def _cmd(fasta: Path, fmt: str = "json") -> list[str]:
        return [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "3",
            "--format",
            fmt,
        ]

    return _cmd
