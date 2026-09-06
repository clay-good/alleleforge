"""Every artifact this tool writes must say what it is.

Four rounds in a row found the same defect one artifact over: the cohort summary TSV,
the standalone off-target payload, the browser's cohort table, and the CRISPR-Bench
leaderboard each carried careful per-row honesty and no statement of what the document
was. Each was missed because the check that would have caught it was keyed to a type —
`DesignReport` renders — and these are not that type.

So this enumerates the artifacts instead of the types. Every writer in `src/` that a
user ends up holding is produced here, through its real path, and asserted to carry
`RESEARCH_USE_CORE`.

`EXEMPT` is the mechanism that keeps it honest: an artifact may be absent from the rule
only with a reason recorded here, and the reason has to survive being read. Two are
exempt today and both are load-bearing decisions, not conveniences.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.report.builder import RESEARCH_USE_CORE

#: The clause every artifact must carry. Short on purpose: the PDF wraps its content
#: stream, so a needle longer than a line would fail there for a reason unrelated to
#: what is being checked. `test_the_needle_is_really_from_the_disclaimer` ties it back
#: to the constant, so a reworded disclaimer cannot leave this passing on a string
#: nothing produces any more.
NEEDLE = "not a medical device"

#: Artifacts deliberately outside the rule, each with the reason.
EXEMPT: dict[str, str] = {
    "bench-result-json": (
        "carries the machine-readable `dataset_is_synthetic` flag beside the score, "
        "and `verify_signature` hashes the whole model, so adding a prose field would "
        "invalidate the signature of every previously signed result and report an "
        "untampered file as 'edited after signing'"
    ),
    "cohort-item-menu-json": (
        "a serialized `RankedMenu`, the library's own type rather than a rendered "
        "artifact; the run that wrote it puts the context in the summary TSV and the "
        "manifest header beside it"
    ),
}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / "ref.fa"
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


def _design(runner: CliRunner, fasta: Path, out: Path, fmt: str) -> str:
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
            "--format",
            fmt,
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return out.read_bytes().decode("latin-1", "replace")


def _cohort_summary(runner: CliRunner, fasta: Path, tmp_path: Path) -> str:
    listing = tmp_path / "cohort.txt"
    listing.write_text("chr2:71:A>C\n")
    out = tmp_path / "summary.tsv"
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "1",
            "--summary-tsv",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return out.read_text()


def _offtarget_json(runner: CliRunner, fasta: Path) -> str:
    result = runner.invoke(
        app,
        [
            "offtarget",
            "TATATATATATACCAATATA",
            "--reference-fasta",
            str(fasta),
            "--on-target",
            "chr2:43-63",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return json.dumps(json.loads(result.stdout))


def _leaderboard(runner: CliRunner, tmp_path: Path, fmt: str) -> str:
    result_json = tmp_path / "bench.json"
    run = runner.invoke(app, ["bench", "run", "cas9-efficiency", "--out", str(result_json)])
    assert run.exit_code == 0, run.output + run.stderr
    out = tmp_path / f"board.{fmt}"
    board = runner.invoke(
        app,
        ["bench", "leaderboard", str(result_json), "--format", fmt, "--out", str(out)],
    )
    assert board.exit_code == 0, board.output + board.stderr
    return out.read_text()


@pytest.mark.parametrize(
    "artifact",
    [
        "design-html",
        "design-pdf",
        "design-tsv",
        "design-json",
        "cohort-summary-tsv",
        "offtarget-json",
        "leaderboard-markdown",
        "leaderboard-html",
    ],
)
def test_the_artifact_states_what_it_is(
    runner: CliRunner, fasta: Path, tmp_path: Path, artifact: str
) -> None:
    if artifact.startswith("design-"):
        fmt = artifact.removeprefix("design-")
        text = _design(runner, fasta, tmp_path / f"menu.{fmt}", fmt)
    elif artifact == "cohort-summary-tsv":
        text = _cohort_summary(runner, fasta, tmp_path)
    elif artifact == "offtarget-json":
        text = _offtarget_json(runner, fasta)
    else:
        text = _leaderboard(runner, tmp_path, artifact.removeprefix("leaderboard-"))

    assert NEEDLE in text, f"{artifact} does not say what it is"
    assert artifact not in EXEMPT, f"{artifact} is both checked and exempt"


def test_the_exemptions_are_still_the_only_ones() -> None:
    """Guard the guard: an exemption must be a decision, not a place to lose one."""
    assert set(EXEMPT) == {"bench-result-json", "cohort-item-menu-json"}
    for artifact, reason in EXEMPT.items():
        assert len(reason) > 80, f"{artifact}'s exemption has no real reason"


def test_the_exempt_bench_result_still_carries_its_machine_readable_flag(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The exemption rests on this flag existing; if it goes, the exemption goes."""
    out = tmp_path / "bench.json"
    result = runner.invoke(app, ["bench", "run", "cas9-efficiency", "--out", str(out)])
    assert result.exit_code == 0, result.output + result.stderr
    payload = json.loads(out.read_text())
    assert payload["dataset_is_synthetic"] is True
    assert "signature" in payload


def test_the_needle_is_really_from_the_disclaimer() -> None:
    """The needle is a literal, so pin that it is still a clause the tool emits."""
    assert NEEDLE in RESEARCH_USE_CORE


def test_the_needle_is_not_vacuous(tmp_path: Path) -> None:
    """A substring present in every file would make every case above pass."""
    listing = tmp_path / "plain.txt"
    listing.write_text("chr2:71:A>C\n")
    assert NEEDLE not in listing.read_text()
