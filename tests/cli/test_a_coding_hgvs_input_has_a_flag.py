"""A `c.`/`p.` input was the one form no command could resolve, on a false premise.

The allowance read: "c./p. inputs need a projector from the `hgvs` library, which is not a
dependency and has no file a flag could name". Both halves are true. Neither is a reason —
this CLI offers every other optional capability behind a boolean flag and a named
`MissingDependencyError`: `--trained-efficiency` needs the `cas9-rs3` extra, `--trained-prime`
needs a consent-gated download, `--summary-parquet` needs `pyarrow`, the VCF fast path needs
`cyvcf2`. An implementation constraint had been generalized into "this surface has no way to
supply it", and three documents repeated the sentence.

`--hgvs` is that flag. It also targets the *run's* assembly rather than the `hgvs` library's
`GRCh38` default: a `c.` expression projected onto GRCh38 and then designed against an hg19
or T2T FASTA is a wrong locus that every later check would take at face value.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, _hgvs_adapter, app

_HGVS = "NM_000059.3:c.1234A>G"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "chr13.fa"
    path.write_text(">chr13\n" + "ACGTTGCAAGGCTTACCGTA" * 30 + "\n")
    return path


def test_every_command_that_takes_a_variant_offers_it() -> None:
    """Parity: the flag is useless on `resolve` alone, and worst missing from `batch`."""
    root = typer.main.get_command(app)
    for command in ("resolve", "design", "batch"):
        options = {
            opt
            for param in root.commands[command].params  # type: ignore[attr-defined]
            for opt in param.opts
        }
        assert "--hgvs" in options, command


def test_without_the_flag_the_refusal_names_it(fasta: Path) -> None:
    result = CliRunner().invoke(app, ["resolve", _HGVS, "--reference-fasta", str(fasta)])
    assert result.exit_code == ExitCode.USAGE
    output = result.output + result.stderr
    assert "--hgvs" in output, output
    # And what a caller on another surface can do instead.
    assert "chrom:pos:ref>alt" in output, output


def test_the_projector_targets_the_runs_assembly() -> None:
    """`--build hg19` must not project onto GRCh38 and design against hg19 bases."""
    adapter = _hgvs_adapter(True, "hg19")
    assert adapter is not None
    projector: Any = adapter._projector  # noqa: SLF001 - asserting what was constructed
    assert projector._assembly == "GRCh37"  # noqa: SLF001
    assert _hgvs_adapter(True, "hg38")._projector._assembly == "GRCh38"  # noqa: SLF001
    assert _hgvs_adapter(False, "hg38") is None


def test_the_missing_package_is_reported_as_unavailable(fasta: Path) -> None:
    """The optional-dependency idiom: a named exit code, not a traceback.

    `hgvs` is not installed in this environment, which is what makes this the real path
    rather than a simulation of it.
    """
    if importlib.util.find_spec("hgvs") is not None:  # pragma: no cover - not installed here
        pytest.skip("the `hgvs` package is installed, so this is not the missing-dep path")
    result = CliRunner().invoke(app, ["resolve", _HGVS, "--hgvs", "--reference-fasta", str(fasta)])
    assert result.exit_code == ExitCode.UNAVAILABLE, result.output + result.stderr
    output = result.output + result.stderr
    assert "hgvs" in output and "Traceback" not in output


def test_design_and_batch_reach_the_projector_too(fasta: Path, tmp_path: Path) -> None:
    """A flag on `resolve` alone would be the same gap one command over."""
    if importlib.util.find_spec("hgvs") is not None:  # pragma: no cover - not installed here
        pytest.skip("the `hgvs` package is installed, so this is not the missing-dep path")
    cohort = tmp_path / "cohort.txt"
    cohort.write_text(_HGVS + "\n")
    runs = (
        ["design", _HGVS, "--hgvs", "--reference-fasta", str(fasta), "--no-offtarget"],
        ["batch", str(cohort), "--hgvs", "--reference-fasta", str(fasta), "--no-offtarget"],
    )
    for argv in runs:
        result = CliRunner().invoke(app, argv)
        output = result.output + result.stderr
        # The projector was reached: what fails is the optional package behind it, by
        # name. Without the wiring the run would refuse the input itself instead.
        assert "hgvs" in output, (argv, output)
        assert "needs a projector" not in output, (argv, output)


def test_a_genomic_hgvs_input_never_needed_any_of_this(fasta: Path) -> None:
    result = CliRunner().invoke(app, ["resolve", "chr13:g.31G>A", "--reference-fasta", str(fasta)])
    assert result.exit_code == 0, result.output + result.stderr
