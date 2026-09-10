"""`aforge batch genome.fa --reference-fasta genome.fa` read the genome as a cohort.

The two path arguments transposed is one keystroke from the correct command, and the tool
took it literally: 2,001 FASTA lines became 2,001 "variants", every one of them failed, and
the terminal filled with whole 1,000-base sequence lines quoted back as `unrecognized
variant input`. Nothing in that output named the mistake — the exit code said MISSING_DATA
and the summary said `2001 requested — 0 ok`, both of which describe a cohort that happens
to be bad rather than an argument in the wrong slot.

The file announces what it is on its first line. Saying so costs one comparison and names
the flag the genome belongs to.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, _read_variant_list, app


def _fasta(tmp_path: Path) -> Path:
    path = tmp_path / "genome.fa"
    path.write_text(">chr1 assembled\n" + "ACGT" * 250 + "\n" + "ACGT" * 250 + "\n")
    return path


def test_a_fasta_in_the_cohort_slot_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        _read_variant_list(_fasta(tmp_path))
    assert excinfo.value.exit_code == ExitCode.USAGE

    err = capsys.readouterr().err
    assert "FASTA" in err
    # The remedy is the whole point: say which argument the genome belongs to.
    assert "--reference-fasta" in err
    # And do not do the thing that made the original output unreadable.
    assert "ACGTACGT" not in err


def test_a_cohort_is_still_read(tmp_path: Path) -> None:
    """The guard keys on `>`, which no variant expression starts with."""
    path = tmp_path / "cohort.txt"
    path.write_text("# a comment\n\nchr2:71:A>C\nchr2:80:G>T\n")
    assert _read_variant_list(path) == ["chr2:71:A>C", "chr2:80:G>T"]


def test_the_batch_command_refuses_it(tmp_path: Path, runner: CliRunner) -> None:
    """End to end, through the surface where the transposition actually happens."""
    fasta = _fasta(tmp_path)
    result = runner.invoke(app, ["batch", str(fasta), "--reference-fasta", str(fasta)])
    assert result.exit_code == ExitCode.USAGE
    assert "--reference-fasta" in result.stderr
    assert "requested" not in result.stdout
