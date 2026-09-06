"""The accessibility data must be named in provenance, and its track must exist.

`--encode-tracks` supplies the open-chromatin signal that adjusts the efficiency
prediction. Two runs over two bedGraphs differing only in their signal value produced
different efficiencies and **identical provenance**:

    d1.bg (0.9)  ->  efficiency 0.484
    d2.bg (0.1)  ->  efficiency 0.457
    provenance identical: True     datasets: []

`_collect_datasets` is explicitly handed `encode_tracks` alongside the haplotype panel
and the patient variants, and `_attach_source` pins gnomAD and the haplotype panel by
content hash — the ENCODE loader was the one that never tagged what it read. The
snapshot recorded `chromatin_track`, a *name*, which is the same mistake as recording
`reference_build` and calling the genome identified.

The second defect is the same flag from the other side. `--chromatin-track` naming a
track absent from the file raised `KeyError` inside the chemistry, which was caught as
a decline reason: an **empty menu and exit 0**, with the cause buried in a rationale
paragraph. `_load_encode_tracks` exists to stop a silently-unapplied chromatin
adjustment — it checked that the pair was given together and never that the name
resolved, so the guard covered the typo it was written for and not the one next to it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def prime_fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    return fasta


def _bedgraph(tmp_path: Path, name: str, value: float) -> Path:
    path = tmp_path / name
    path.write_text(f"dnase\tchr2\t0\t140\t{value}\n")
    return path


def _design(
    runner: CliRunner, fasta: Path, out: Path, tracks: Path, track: str
) -> tuple[int, dict, str]:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "1",
            "--encode-tracks",
            str(tracks),
            "--chromatin-track",
            track,
            "--out",
            str(out),
        ],
    )
    payload = json.loads(out.read_text()) if out.is_file() else {}
    return result.exit_code, payload, result.output + result.stderr


def test_two_accessibility_tracks_do_not_share_a_provenance(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """The data that moved the efficiency number must be named in the record."""
    open_code, open_menu, _ = _design(
        runner, prime_fasta, tmp_path / "a.json", _bedgraph(tmp_path, "a.bg", 0.9), "dnase"
    )
    closed_code, closed_menu, _ = _design(
        runner, prime_fasta, tmp_path / "b.json", _bedgraph(tmp_path, "b.bg", 0.1), "dnase"
    )
    assert open_code == closed_code == 0
    # The premise: the two runs really do disagree about the answer.
    assert (
        open_menu["candidates"][0]["efficiency"]["value"]
        != closed_menu["candidates"][0]["efficiency"]["value"]
    )

    names = {d["name"] for d in open_menu["provenance"]["datasets"]}
    assert "encode-tracks" in names, open_menu["provenance"]["datasets"]
    assert open_menu["provenance"]["datasets"] != closed_menu["provenance"]["datasets"]


def test_the_encode_descriptor_pins_the_bytes(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """Pinned by content hash, like gnomAD and the haplotype panel beside it."""
    _, menu, _ = _design(
        runner, prime_fasta, tmp_path / "a.json", _bedgraph(tmp_path, "a.bg", 0.9), "dnase"
    )
    encode = next(d for d in menu["provenance"]["datasets"] if d["name"] == "encode-tracks")
    assert isinstance(encode["sha256"], str) and len(encode["sha256"]) == 64
    assert encode["version"].startswith("sha256:")


def test_a_track_name_that_is_not_in_the_file_is_refused(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """Not an empty menu and exit 0: the name is checked where it is supplied."""
    code, _, output = _design(
        runner, prime_fasta, tmp_path / "w.json", _bedgraph(tmp_path, "a.bg", 0.9), "typo"
    )
    assert code == ExitCode.USAGE, output
    assert "typo" in output
    # And it names what is available, so the fix does not need a second command.
    assert "dnase" in output


def test_a_file_with_no_usable_track_is_refused(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """A bedGraph whose every line was skipped yields no tracks, and must say so.

    The parser drops lines beginning `track`/`browser`/`#` as UCSC directives, so a
    file whose first column happens to be one of those parses to nothing at all.
    """
    empty = tmp_path / "directives.bg"
    empty.write_text("track\tchr2\t0\t140\t0.9\n")
    code, _, output = _design(runner, prime_fasta, tmp_path / "e.json", empty, "track")
    assert code == ExitCode.USAGE, output
    assert "no tracks" in output.lower() or "none" in output.lower()
