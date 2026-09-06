"""The build-mismatch refusal names a command; the command's output feeds the next one.

`resolve` refuses a record whose native assembly disagrees with the requested build —
relabeling a coordinate designs a guide at the wrong place — and tells the caller:

    lift the coordinates to 'hg38' before resolving rather than relabeling them —
    `aforge lift <locus> --chain <file> --from hg19 --to hg38`

`lift` in turn documents that it "prints `input<TAB>output` per locus, in order, in the
same locus form `design --region` accepts, so the result pipes straight back in".

Two claims across three commands, and nothing ran them end to end: that the named flags
exist, that a real chain file produces a mapped locus, and that the locus it prints is
accepted verbatim by the command it says to hand it to. A remedy whose output the next
step rejects is the same dead end as no remedy at all.

Also pinned: an unmappable locus prints `UNMAPPED` and exits non-zero. Dropping it would
silently shrink a search — the smaller region finds fewer off-targets and reads as a
cleaner guide.
"""

from __future__ import annotations

import inspect
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.variant import resolver

_CHAIN = Path(__file__).resolve().parents[1] / "genome" / "fixtures" / "forward.chain"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def reference(tmp_path: Path) -> Path:
    """A FASTA on the chain's *target* contig, so a lifted locus can be searched."""
    rng = random.Random(3)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chrA\n" + "".join(rng.choice("ACGT") for _ in range(1_000)) + "\n")
    return fasta


def test_the_refusal_names_flags_lift_accepts() -> None:
    """The remedy string is a command line; every flag in it must exist."""
    from alleleforge.cli.main import lift

    message = inspect.getsource(resolver)
    assert "aforge lift <locus> --chain <file> --from" in message
    options = set(inspect.signature(lift).parameters)
    assert {"chain", "loci"} <= options
    assert "from_build" in options or "from" in " ".join(options)


def test_lift_maps_a_locus_and_the_region_flag_takes_it(runner: CliRunner, reference: Path) -> None:
    lifted = runner.invoke(
        app, ["lift", "chr1:10-60", "--chain", str(_CHAIN), "--from", "hg19", "--to", "hg38"]
    )
    assert lifted.exit_code == 0, lifted.output + lifted.stderr
    source, target = lifted.stdout.strip().split("\t")
    assert source.startswith("chr1:10-60")
    assert target != "UNMAPPED"

    # The claim: the printed locus is what `--region` accepts, unmodified.
    searched = runner.invoke(
        app,
        [
            "offtarget",
            "ACGTAACGTTACGTAACGTT",
            "--reference-fasta",
            str(reference),
            "--region",
            target,
            "--json",
        ],
    )
    assert searched.exit_code == 0, searched.output + searched.stderr


def test_an_unmappable_locus_is_named_not_dropped(runner: CliRunner) -> None:
    """A silently shorter list is a smaller search, which reads as a cleaner guide."""
    result = runner.invoke(
        app, ["lift", "chr1:100-200", "--chain", str(_CHAIN), "--from", "hg19", "--to", "hg38"]
    )
    assert "UNMAPPED" in result.stdout
    assert result.exit_code == ExitCode.UNAVAILABLE
    assert "dropped, not approximated" in result.stderr
