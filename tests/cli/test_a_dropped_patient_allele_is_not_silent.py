"""`--patient-vcf` must say which of a person's alleles it did not scan.

`iter_vcf` drops soft-filtered calls and symbolic ALTs, and `pass_only=True` is its
default. `aforge batch` passes a `VcfIngestCounts` and prints the tally, because a
cohort was found to be silently smaller than the file it came from. The patient
off-target path called `list(iter_vcf(path))` and counted nothing.

The asymmetry runs the wrong way. For a cohort a dropped row is one guide fewer, which
shows up as a shorter output. For `--patient-vcf` a dropped row is a **safety check that
was never performed**, and the run then prints the most reassuring thing it can say —
no patient-origin sites — which is indistinguishable from "this person carries nothing
risky". `pass_only`'s rationale is written for the cohort use ("a cohort run should not
design against soft-filtered calls"); the safety use inherited it unexamined, and a
low-confidence call can still create a de-novo PAM in the person who carries it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import alleleforge.variant as variant_pkg
from alleleforge.cli.main import app
from alleleforge.variant.vcf import iter_vcf as _real_iter_vcf


@dataclass
class _FakeVariant:
    """A stand-in for a ``cyvcf2.Variant`` (1-based POS, ``FILTER=None`` means PASS)."""

    CHROM: str
    POS: int
    REF: str
    ALT: list[str]
    ID: str | None = None
    FILTER: str | None = None


@pytest.fixture
def bias_fasta(tmp_path: Path) -> tuple[Path, str]:
    """A spacer with no NRG PAM in the reference; `chr2:33 T>G` creates a de-novo NGG."""
    spacer = "GACCATGCAACCTTGAACGT"
    pad = "T" * 10
    fasta = tmp_path / "bias.fa"
    fasta.write_text(f">chr2\n{pad}{spacer}CGT{pad}\n")
    return fasta, spacer


def _serve(monkeypatch: pytest.MonkeyPatch, records: list[_FakeVariant]) -> None:
    """Route the CLI's VCF read through the real reader over ``records``.

    Only the file opening is stubbed — cyvcf2 is not installed here — so the drop
    counting under test is the shipped code, not a reimplementation of it.
    """

    def fake(source: Any, **kwargs: Any) -> Any:
        return _real_iter_vcf(records, **kwargs)

    monkeypatch.setattr(variant_pkg, "iter_vcf", fake)


def _run(runner: CliRunner, fasta: Path, spacer: str, vcf: Path) -> Any:
    return runner.invoke(
        app,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--patient-vcf",
            str(vcf),
            "--json",
        ],
    )


def test_a_soft_filtered_allele_that_is_not_scanned_is_named(
    runner: CliRunner, bias_fasta: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dangerous case: the only risky allele is soft-filtered, so nothing is found.

    Without the note this run is byte-identical to a scan of a person who carries no
    risk at all, which is the one conclusion the output must not support by accident.
    """
    fasta, spacer = bias_fasta
    _serve(monkeypatch, [_FakeVariant("chr2", 33, "T", ["G"], FILTER="LowQual")])
    vcf = tmp_path / "patient.vcf"
    vcf.write_text("##fileformat=VCFv4.2\n")

    result = _run(runner, fasta, spacer, vcf)

    assert result.exit_code == 0
    assert json.loads(result.stdout)["n_sites"] == 0, "the allele was filtered out"
    assert "NOT scanned for off-targets" in result.stderr
    assert "1 of 1" in result.stderr


def test_the_scanned_allele_is_still_found_and_the_drop_still_reported(
    runner: CliRunner, bias_fasta: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PASS allele must still nominate its site; the note is additional, not a swap."""
    fasta, spacer = bias_fasta
    _serve(
        monkeypatch,
        [
            _FakeVariant("chr2", 33, "T", ["G"], FILTER=None),
            _FakeVariant("chr2", 12, "T", ["A"], FILTER="LowQual"),
        ],
    )
    vcf = tmp_path / "patient.vcf"
    vcf.write_text("##fileformat=VCFv4.2\n")

    result = _run(runner, fasta, spacer, vcf)

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["n_sites"] == 1
    assert body["sites"][0]["origin"] == "patient"
    assert "1 of 2" in result.stderr


def test_a_vcf_with_nothing_dropped_says_nothing(
    runner: CliRunner, bias_fasta: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A note printed unconditionally would be noise, and would stop being read."""
    fasta, spacer = bias_fasta
    _serve(monkeypatch, [_FakeVariant("chr2", 33, "T", ["G"], FILTER=None)])
    vcf = tmp_path / "patient.vcf"
    vcf.write_text("##fileformat=VCFv4.2\n")

    result = _run(runner, fasta, spacer, vcf)

    assert result.exit_code == 0
    assert json.loads(result.stdout)["n_sites"] == 1
    assert "dropped" not in result.stderr
