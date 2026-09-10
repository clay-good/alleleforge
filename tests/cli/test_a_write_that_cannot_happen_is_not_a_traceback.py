"""The output path checks were about shape; a read-only directory is not a shape.

An earlier round moved the *kind* checks before the work — a `--summary-tsv` pointing at a
directory should not be discovered after three hundred variants. What it could not catch is
a path of exactly the right shape that cannot be written: a read-only mount, a full disk, a
filesystem that refuses the provenance sidecar's name. Those arrived as a raw
`PermissionError` traceback **after** the whole design, which is the worst moment for the one
failure that loses the work.

    $ aforge design chr11:2004:T>A --reference-fasta g.fa --format html --out ro/r.html
    PermissionError: [Errno 1] Operation not permitted: 'ro/r.html.provenance.json'

Not hypothetical: this project's own `docker-compose.yml` mounts a volume read-only.

Both halves. Writability is checked up front, so the ordinary case costs nothing; and the
write is still guarded, because `os.access` can be wrong under ACLs or as root — an advisory
pre-check is not a substitute for handling the failure.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    path = tmp_path / "g.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path.write_text(">chr2\n" + "".join(seq) + "\n")
    return path


@pytest.fixture
def read_only(tmp_path: Path) -> Path:
    directory = tmp_path / "ro"
    directory.mkdir()
    directory.chmod(0o555)
    yield directory
    directory.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes to a read-only directory anyway")
def test_a_read_only_out_is_refused_before_the_design(
    runner: CliRunner, genome: Path, read_only: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--format",
            "html",
            "--out",
            str(read_only / "r.html"),
        ],
    )
    assert result.exit_code == ExitCode.MISSING_DATA, result.stderr
    assert "not writable" in result.stderr
    assert "Traceback" not in result.stderr
    # Before the run, which is the point: nothing was designed.
    assert result.stdout.strip() == ""


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes to a read-only directory anyway")
def test_a_cohorts_output_paths_are_checked_before_the_cohort(
    runner: CliRunner, genome: Path, read_only: Path, tmp_path: Path
) -> None:
    cohort = tmp_path / "cohort.txt"
    cohort.write_text("chr2:71:A>C\n")
    for flag, target in (
        ("--summary-tsv", read_only / "s.tsv"),
        ("--output-dir", read_only / "menus"),
        ("--manifest", read_only / "m.jsonl"),
    ):
        result = runner.invoke(
            app,
            [
                "batch",
                str(cohort),
                "--reference-fasta",
                str(genome),
                "--no-offtarget",
                flag,
                str(target),
            ],
        )
        assert result.exit_code == ExitCode.MISSING_DATA, (flag, result.stderr)
        assert "not writable" in result.stderr, flag
        assert "requested" not in result.stdout, flag


def test_a_write_that_fails_anyway_is_reported_not_raised(
    runner: CliRunner, genome: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`os.access` is advisory — under ACLs or as root it says yes and the write fails."""
    out = tmp_path / "r.html"
    original = Path.write_bytes

    def refuse(self: Path, data: bytes) -> int:
        if self == out:
            raise PermissionError(13, "Permission denied")
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", refuse)
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--format",
            "html",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == ExitCode.MISSING_DATA, result.stderr
    assert "could not write" in result.stderr
    # It says the work was done, so the reader knows what a re-run costs.
    assert "The design finished" in result.stderr
    assert "Traceback" not in result.stderr


def test_a_writable_path_still_works(runner: CliRunner, genome: Path, tmp_path: Path) -> None:
    out = tmp_path / "r.html"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(genome),
            "--no-offtarget",
            "--format",
            "html",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == ExitCode.OK, result.stderr
    assert out.is_file()
    assert out.with_suffix(out.suffix + ".provenance.json").is_file()
