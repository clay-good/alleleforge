"""Run the sentence, not just the refusal.

A refusal is judged on whether it fires and on what it says. What it *tells you to do* is a
second piece of software, executed by a person, and nothing was executing it — which is how
`--no-resume`, named by three messages, came to append a second record per item to the
manifest it ran into.

Each row here is one refusal a user actually meets, and the remedy its message gives. The
row asserts three things in order: the wrong command fails, its message names the remedy
(so a message that stops offering it fails here rather than drifting away from this table),
and the remedy command then succeeds.

The table is written out because there is no deriving "what does this sentence tell me to
do" — but it is *tied* to the messages by the middle assertion, which is the part that
would otherwise go stale.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

#: `(name, wrong args, the token its message must name, remedy args)`. Args are built from
#: a fixture directory so each row can name real files.
_Rows = Callable[[Path], list[tuple[str, list[str], str, list[str]]]]


def _rows(d: Path) -> list[tuple[str, list[str], str, list[str]]]:
    genome, cohort, sites = str(d / "g.fa"), str(d / "cohort.txt"), str(d / "sites.tsv")
    return [
        (
            "a genome handed to batch as the cohort",
            ["batch", genome, "--reference-fasta", genome],
            "--reference-fasta",
            ["batch", cohort, "--reference-fasta", genome, "--no-offtarget"],
        ),
        (
            "a variant handed to batch as the file",
            ["batch", "chr2:71:A>C", "--reference-fasta", genome],
            "aforge design",
            ["design", "chr2:71:A>C", "--reference-fasta", genome, "--no-offtarget"],
        ),
        (
            "a gnomAD sites file handed to --dbsnp",
            [
                "design",
                "chr2:71:A>C",
                "--reference-fasta",
                genome,
                "--no-offtarget",
                "--dbsnp",
                sites,
            ],
            "rsid  chrom  pos  ref  alt",
            [
                "design",
                "rs1",
                "--reference-fasta",
                genome,
                "--no-offtarget",
                "--dbsnp",
                str(d / "dbsnp.tsv"),
            ],
        ),
        (
            "a report whose provenance is in a sidecar",
            ["verify", str(d / "r.html")],
            "aforge verify",
            ["verify", str(d / "r.html.provenance.json")],
        ),
    ]


@pytest.fixture
def fixtures(tmp_path: Path) -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    (tmp_path / "g.fa").write_text(">chr2\n" + "".join(seq) + "\n")
    (tmp_path / "cohort.txt").write_text("chr2:71:A>C\n")
    (tmp_path / "sites.tsv").write_text("#chrom\tpos\tref\talt\taf\nchr2\t71\tA\tC\t0.02\n")
    (tmp_path / "dbsnp.tsv").write_text("#rsid\tchrom\tpos\tref\talt\nrs1\tchr2\t71\tA\tC\n")
    written = CliRunner().invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(tmp_path / "g.fa"),
            "--no-offtarget",
            "--format",
            "html",
            "--out",
            str(tmp_path / "r.html"),
        ],
    )
    assert written.exit_code == ExitCode.OK, written.stderr
    return tmp_path


@pytest.mark.parametrize("index", range(len(_rows(Path("/nonexistent")))))
def test_the_refusal_names_a_remedy_and_the_remedy_works(index: int, fixtures: Path) -> None:
    name, wrong, token, remedy = _rows(fixtures)[index]
    runner = CliRunner()

    refused = runner.invoke(app, wrong)
    assert refused.exit_code != ExitCode.OK, f"{name}: the wrong command succeeded"
    message = refused.stdout + refused.stderr
    assert token in message, f"{name}: the message no longer names {token!r}:\n{message[:400]}"

    followed = runner.invoke(app, remedy)
    assert followed.exit_code == ExitCode.OK, (
        f"{name}: the remedy its message names does not work:\n{followed.stderr[:400]}"
    )


def test_the_table_is_not_empty() -> None:
    """A table that lost its rows would pass every case above."""
    assert len(_rows(Path("/nonexistent"))) >= 4
