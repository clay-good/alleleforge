"""`aforge lift` promises its output "pipes straight back in" to `--region`.

That is a checkable claim and nothing checked it. The two commands are on opposite sides
of the tool -- `lift` formats a `GenomicInterval`, `--region` parses one -- and the
promise is the only reason the liftover is useful from a shell at all: the documented
remedy for a build mismatch is to lift the panel and re-run the design against it.

Also pins the behaviors the command's own help commits to: an unmappable locus prints
`UNMAPPED` rather than being dropped, because a silently shorter panel is a smaller
search, and the run exits non-zero.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.types.sequence import GenomicInterval

pytest.importorskip("pyliftover")

#: An identity chain over one contig: every base of chr1 maps to itself, except that
#: the mapped block stops at 1,000 -- so a locus past it does not lift.
MAPPED_BASES = 1_000


@pytest.fixture
def identity_chain(tmp_path: Path) -> Path:
    chain = tmp_path / "identity.chain"
    chain.write_text(
        f"chain 1000 chr1 {MAPPED_BASES} + 0 {MAPPED_BASES} "
        f"chr1 {MAPPED_BASES} + 0 {MAPPED_BASES} 1\n{MAPPED_BASES}\n\n"
    )
    return chain


def _lift(chain: Path, *loci: str) -> object:
    return CliRunner().invoke(
        app, ["lift", *loci, "--chain", str(chain), "--from", "hg19", "--to", "hg38"]
    )


def test_the_output_parses_as_a_region(identity_chain: Path) -> None:
    result = _lift(identity_chain, "chr1:100-120")
    assert result.exit_code == ExitCode.OK, result.output

    line = result.output.strip().splitlines()[0]
    source, lifted = line.split("\t")
    assert lifted != "UNMAPPED", result.output
    # The claim: this is the same locus form `--region` accepts.
    parsed = GenomicInterval.parse(lifted)
    assert (parsed.chrom, parsed.start, parsed.end) == ("chr1", 100, 120)
    # ...and so is the echoed input, so a failed line is as pipeable as a good one.
    GenomicInterval.parse(source)


def test_an_unmappable_locus_is_named_not_dropped(identity_chain: Path) -> None:
    """A silently shorter panel is a smaller search -- the reassuring direction."""
    result = _lift(identity_chain, "chr1:100-120", "chr1:5000-5020")

    lines = [line for line in result.output.splitlines() if "\t" in line]
    assert len(lines) == 2, f"a locus was dropped: {result.output}"
    assert lines[1].endswith("UNMAPPED")
    assert result.exit_code != ExitCode.OK, "an unmapped locus must not exit 0"


def test_the_error_names_the_builds_and_the_count(identity_chain: Path) -> None:
    result = _lift(identity_chain, "chr1:100-120", "chr1:5000-5020")
    assert "1 of 2 loci did not lift" in result.output
    assert "hg19 to hg38" in result.output
    assert "dropped, not approximated" in result.output


def test_a_missing_chain_file_is_a_clear_error(tmp_path: Path) -> None:
    result = _lift(tmp_path / "nope.chain", "chr1:100-120")
    assert result.exit_code == ExitCode.MISSING_DATA
    assert "chain file not found" in result.output
    assert "Traceback" not in result.output
