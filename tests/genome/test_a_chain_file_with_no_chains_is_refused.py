"""A chain file that is not one reported every locus as absent from the target build.

`pyliftover` parses any text and keeps whatever chain records it finds, so a file that is
not a chain file — the gnomAD TSV one flag over, an HTML error page a download saved, a
truncated `.gz` — builds a liftover with **zero** chains:

    $ aforge lift chr2:0-20(+) --from hg38 --to hg19 --chain frequencies.tsv
    chr2:0-20(+)  UNMAPPED
    error: 1 of 1 loci did not lift from hg38 to hg19; they are dropped, not approximated

Every sentence there is true of a locus that genuinely has no hg19 equivalent, which is
what a reader will conclude. That is a *wrong* answer rather than a missing one, from the
one command whose whole job is to tell you where a locus lives in another assembly — and
the answer a reader is least equipped to doubt, since "this region is not in the older
build" is a real and common thing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyliftover")

from alleleforge.genome.coordinates import Liftover  # noqa: E402

_CHAIN = "chain 1000 chr2 300 + 0 300 chr2 300 + 0 300 1\n300\n\n"


def test_a_file_with_no_chains_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "frequencies.tsv"
    path.write_text("#chrom\tpos\tref\talt\taf\nchr11\t2100\tA\tG\t0.02\n")
    with pytest.raises(ValueError) as excinfo:
        Liftover.from_chain_file(path, source_build="hg38", target_build="hg19")
    message = str(excinfo.value)
    assert "no liftover chains" in message
    # It says what the silence would have meant, and what the right file is called.
    assert "would come back unmapped" in message
    assert "hg38ToHg19.over.chain.gz" in message


def test_an_empty_file_is_the_same_case(tmp_path: Path) -> None:
    path = tmp_path / "truncated.chain"
    path.write_text("")
    with pytest.raises(ValueError, match="no liftover chains"):
        Liftover.from_chain_file(path, source_build="hg38", target_build="hg19")


def test_a_real_chain_file_still_builds(tmp_path: Path) -> None:
    """The half a refusal-only test cannot see."""
    path = tmp_path / "hg38ToHg19.over.chain"
    path.write_text(_CHAIN)
    lifted = Liftover.from_chain_file(path, source_build="hg38", target_build="hg19")
    assert lifted.convert_position("chr2", 10) is not None


def test_the_cli_refuses_it_by_name(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from alleleforge.cli.main import ExitCode, app

    path = tmp_path / "frequencies.tsv"
    path.write_text("#chrom\tpos\tref\talt\taf\n")
    result = CliRunner().invoke(
        app,
        ["lift", "chr2:0-20(+)", "--from", "hg38", "--to", "hg19", "--chain", str(path)],
    )
    assert result.exit_code == ExitCode.MISSING_DATA, result.stderr
    assert "no liftover chains" in result.stderr
    assert "UNMAPPED" not in result.stdout
