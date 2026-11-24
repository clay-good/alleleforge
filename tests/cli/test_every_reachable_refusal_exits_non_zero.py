"""The rest of the `typer.Exit` class: every site a shell can actually reach.

Third and last file closing the class R691 named. In `cli/main.py`, deleting a
`raise typer.Exit(...)` leaves the `_echo_err` above it running, so the error prints with
the right wording and the process exits **0** — invisible to any test that asserts on
stderr text. R691 pinned 3 sites, R693 the 11 in the `bench` family, and this pins the
18 of the remaining 28 that are reachable from a command line.

The ten that are not reachable are listed here rather than left to be rediscovered,
because "untested" and "unreachable" are different facts and the round log should not
have to be consulted to tell them apart:

* `1766`, `2455` — the Parquet writer's `MissingDependencyError`. Fires only when
  `polars` is absent; it is installed here, so no test can reach these without
  uninstalling the writer.
* `3459` — liftover's `ImportError`. `pyliftover` is installed; also `pragma: no cover`.
* `1188` — `--patient-vcf`'s read failure. Shadowed by the arm above it: `cyvcf2` is
  absent in this environment, so every VCF path exits `UNAVAILABLE` for the missing
  extra before a read is ever attempted.
* `783` — `--config`'s `OSError`. Needs `is_file()` to be true and the read to then
  fail. Typer applies `readable=True` to `Path` options by default, so an unreadable
  file is rejected with Typer's own usage error before the command body runs, and a
  directory takes the `is_file()` branch at `766` instead. What is left is a genuine
  I/O error or a race between the check and the read.
* `825` — `_guarded_write`'s `OSError`. Unreachable *by design*: the writability
  precheck in `_check_output_paths` fires first, and this site's own comment explains it
  is the backstop for when `os.access` is wrong (ACLs, or running as root).
* `476`, `1716` — the `--vep` arms, which need Ensembl's REST service to fail a live
  call. `1719`, `1722` — `design`'s `MissingDependencyError` and `ValueError` arms,
  which no flag combination reaches with this environment's dependencies present.

Two more are reachable but **measurably equivalent** — deleting them changes nothing a
caller can see — and are recorded here rather than chased:

* `366` (`_load_settings`) — masked by `121`. Both turn a malformed setting into `USAGE`
  with the same message, and `design` reaches both, so removing one leaves the other to
  report identically.
* `677` (`_parse_weights`'s type branch) — removing the raise still ends in
  `SystemExit(ExitCode.USAGE)` with byte-identical stderr; a later consumer of the same
  config refuses in the same terms. The mechanism is not pinned down, the equivalence is.

Both were confirmed by running the command against clean and mutated source and
comparing exit code, exception and full stderr. That comparison is also how five of
these tests got their `_assert_one_refusal` check: the first draft asserted only the code
and the message, and five mutants survived it because deleting a raise leaves the exit
code untouched and adds a *second* error line. An earlier draft of the comparison said
all seven were equivalent — it was running stale bytecode, having not cleared
`__pycache__` between writes, and measured nothing. Clearing it moved five of the seven
from "equivalent" to "distinguishable".

One trap this file exists to avoid, recorded in R691: `ExitCode.USAGE` is `2`, and Typer
*also* exits 2 when it rejects an invocation outright. So a test with a misspelled flag
passes its exit-code assertion having executed nothing. Every case below therefore
asserts the project's own message as well as the code — and three of these triggers were
found only because the message check failed while the code check passed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.config import reset_settings


def _text(result: object) -> str:
    """Both streams: these refusals go to stderr and the runner keeps them apart."""
    return (getattr(result, "output", "") or "") + (getattr(result, "stderr", "") or "")


def _error_lines(result: object) -> list[str]:
    """The `error:` lines on stderr, which is what a cascade shows up in.

    Several of these guards sit immediately above a sibling whose condition is also true
    — `parent.exists()` then `parent.is_dir()`, a missing config then the read that
    fails. Deleting the `raise` lets the second one fire as well, so the exit code is
    unchanged and the *count* of error lines is what moves. A test asserting only the
    code and the text passes against that mutant; asserting that a single mistake
    produces a single message is what catches it, and it is the better contract anyway.
    """
    stderr = getattr(result, "stderr", "") or ""
    return [line for line in stderr.splitlines() if line.strip().startswith("error:")]


def _assert_one_refusal(result: object, fragment: str) -> None:
    """One mistake, one message, naming the thing that was wrong."""
    lines = _error_lines(result)
    assert len(lines) == 1, (
        f"expected a single refusal, got {len(lines)}: a cascade means the guard that "
        "should have stopped here did not, and the next condition was true as well",
        lines,
    )
    assert fragment in lines[0], (fragment, lines[0])


def _design(prime_fasta: Path, *extra: str) -> list[str]:
    """A `design` invocation that succeeds, plus whatever is being made to fail.

    Spelled out rather than fixtured because the variant is *positional* here — writing
    it as `--variant` is what made three earlier tests pass against Typer's own usage
    error instead of the guard they named.
    """
    return [
        "design",
        "chr2:71:A>C",
        "--reference-fasta",
        str(prime_fasta),
        "--intent",
        "install",
        *extra,
    ]


def test_the_premise_a_clean_design_exits_zero(runner: CliRunner, prime_fasta: Path) -> None:
    """Without this, every refusal below could be an unrelated failure."""
    result = runner.invoke(app, _design(prime_fasta))
    assert result.exit_code == ExitCode.OK, _text(result)


# -- settings, read through two different call sites ---------------------------


@pytest.mark.parametrize(
    "argv_for, command",
    [("design", "design"), ("resolve", "resolve")],
    ids=["via-_load_settings", "via-reference_build"],
)
def test_a_malformed_setting_is_a_usage_error_from_either_call_site(
    runner: CliRunner,
    prime_fasta: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv_for: str,
    command: str,
) -> None:
    """Two sites raise this, with a byte-identical message, and only one was reached.

    `_load_settings` (`main.py:366`) and `GlobalState.reference_build` (`:121`) both turn
    a malformed setting into `USAGE`. They are reached by different commands: only
    `design` and `batch` call `_load_settings`, while `resolve` reads `reference_build`
    directly. A test through `design` alone leaves `:121` unpinned and looks like it
    covered both, because the text it asserts is the same — the duplicate-message trap
    this project has already been bitten by once.
    """
    monkeypatch.setenv("ALLELEFORGE_INTERVAL_LEVEL", "not-a-number")
    # The settings singleton is process-wide and loaded once, so a sibling test that
    # already read it leaves the bad value unseen and this exits 0 — which is the shape
    # of the very bug being tested, arriving from test ordering rather than from the
    # code. Reset so the guard is reached on its own terms; `reset_settings` exists for
    # this and the next reader re-resolves the environment.
    reset_settings()
    monkeypatch.setattr(
        "alleleforge.config._SETTINGS", None, raising=False
    )  # belt and braces: the module global is what `get_settings` consults

    argv = (
        _design(prime_fasta)
        if command == "design"
        else ["resolve", "chr2:71:A>C", "--reference-fasta", str(prime_fasta)]
    )
    result = runner.invoke(app, argv)

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    assert "invalid AlleleForge configuration" in _text(result), _text(result)


# -- the config file -----------------------------------------------------------


def test_a_config_file_that_is_not_there_is_missing_data(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    result = runner.invoke(app, _design(prime_fasta, "--config", str(tmp_path / "nope.toml")))
    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    # Exactly one: without the raise, the read below fails too and reports a second
    # time with the same exit code, so the count is the only thing that moves.
    _assert_one_refusal(result, "config file not found")


def test_a_directory_given_as_a_config_takes_the_same_branch(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """`is_file()` is false for a directory, so this is the `766` branch, not an OSError.

    Pinned because it is the obvious way to try to provoke the *sibling* `OSError` arm at
    `783`, and it does not: knowing that is what makes `783`'s unreachability a finding
    rather than an omission.
    """
    directory = tmp_path / "conf.d"
    directory.mkdir()
    result = runner.invoke(app, _design(prime_fasta, "--config", str(directory)))
    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    assert "config file not found" in _text(result), _text(result)


@pytest.mark.parametrize(
    "body, expected_fragment",
    [
        ("populations = 5\n", "populations must be a comma-separated string or an array"),
        ("weights = 5\n", "weights must be"),
        ("weights = [1.0, 2.0]\n", "weights expects"),
    ],
    ids=["populations-wrong-type", "weights-wrong-type", "weights-wrong-length"],
)
def test_a_config_value_of_the_wrong_shape_is_a_usage_error(
    runner: CliRunner,
    prime_fasta: Path,
    tmp_path: Path,
    body: str,
    expected_fragment: str,
) -> None:
    """These guards exist because the *config file* is untyped where the flag is not.

    `--populations` and `--weights` are typed options, so a shell cannot pass an integer.
    A TOML file can, and `_parse_populations`/`_parse_weights` take `Any` for exactly
    that reason — which is why a test driving only the flags would never reach them.
    """
    config = tmp_path / "run.toml"
    config.write_text(body)
    result = runner.invoke(app, _design(prime_fasta, "--config", str(config)))

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    assert expected_fragment in _text(result), _text(result)


# -- the reference --------------------------------------------------------------


def test_a_command_with_no_reference_at_all_is_missing_data(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flag is optional so the environment can supply it; with neither, refuse."""
    monkeypatch.setenv("ALLELEFORGE_REFERENCE_FASTA", "")
    result = runner.invoke(app, ["design", "chr2:71:A>C", "--intent", "install"])

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    assert "--reference-fasta is required" in _text(result), _text(result)


def test_a_reference_path_that_does_not_exist_is_missing_data(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The sibling guard two lines below the one above, and a different user mistake.

    `_load_reference` refuses twice: once for no reference at all, once for a path that
    is not there. They share an exit code, so a test covering only the first looks like
    it covered both. This is the second — a typo'd or moved FASTA — and it asserts a
    single refusal because, without the raise, construction proceeds on the missing path
    and fails again with a second message.
    """
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--intent",
            "install",
            "--reference-fasta",
            str(tmp_path / "moved.fa"),
        ],
    )

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    _assert_one_refusal(result, "reference FASTA not found")


# -- paired flags, and files that are the wrong thing ---------------------------


def test_encode_tracks_without_a_track_name_is_a_usage_error(
    runner: CliRunner, prime_fasta: Path
) -> None:
    """Half of a two-flag feature is a mistake, not a default to guess at."""
    result = runner.invoke(app, _design(prime_fasta, "--encode-tracks", str(prime_fasta)))
    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    assert "must be given together" in _text(result), _text(result)


def test_an_encode_file_defining_no_tracks_is_a_usage_error(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """A file of only UCSC directives parses to nothing, which is not an empty answer.

    Silently proceeding would run the open-chromatin adjustment against no data and
    report efficiencies as though it had been applied.
    """
    tracks = tmp_path / "empty.bedgraph"
    tracks.write_text("# a comment\ntrack name=dnase\nbrowser position chr2\n")
    result = runner.invoke(
        app, _design(prime_fasta, "--encode-tracks", str(tracks), "--chromatin-track", "dnase")
    )

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    _assert_one_refusal(result, "defines no tracks")
    # The remedy names the format, since "no tracks" in a file full of lines is baffling.
    assert "track chrom start end value" in _text(result), _text(result)


@pytest.mark.parametrize(
    "flag, fragment",
    [
        ("--encode-tracks", "could not read --encode-tracks"),
        ("--regions-bed", "could not read --regions-bed"),
        ("--clinvar", "could not read --clinvar"),
    ],
)
def test_a_directory_where_a_file_belongs_is_missing_data(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path, flag: str, fragment: str
) -> None:
    """The reachable route into the `OSError` arms, and the only one.

    Typer applies `readable=True` to `Path` options, so an unreadable *file* never gets
    this far — it is rejected with Typer's own exit 2. A directory is readable, so the
    option validates and `open()` then raises `IsADirectoryError`. That is what makes
    these three arms testable while `--config`'s equivalent at `783` is not: `--config`
    checks `is_file()` first and sends a directory down a different branch.
    """
    directory = tmp_path / "a_directory"
    directory.mkdir()
    extra = [flag, str(directory)]
    if flag == "--encode-tracks":
        extra += ["--chromatin-track", "dnase"]

    result = runner.invoke(app, _design(prime_fasta, *extra))

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    assert fragment in _text(result), _text(result)


def test_a_regions_bed_naming_an_absent_contig_is_a_usage_error(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """A BED for another assembly restricts the search to nothing.

    Without the refusal the run proceeds over an empty region set and reports a clean
    result — the shape of wrong answer this project guards hardest against, since zero
    off-target sites reads as a perfect guide.
    """
    bed = tmp_path / "regions.bed"
    bed.write_text("chrZZ\t0\t10\n")
    result = runner.invoke(app, _design(prime_fasta, "--regions-bed", str(bed)))

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    out = _text(result)
    assert "chrZZ" in out, out
    assert "this reference does not have" in out, out


# -- output paths, checked before the run rather than after ---------------------


def test_an_out_path_in_a_directory_that_does_not_exist_is_a_usage_error(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """Not created silently: `--out reslts/x.json` is a typo far more often than intent."""
    result = runner.invoke(
        app, _design(prime_fasta, "--out", str(tmp_path / "nosuchdir" / "design.json"))
    )
    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    # One message: `parent.is_dir()` on the line below is *also* false for a path that
    # does not exist, so without the raise both fire and the caller gets a cascade.
    _assert_one_refusal(result, "no such directory")


def test_an_out_path_whose_parent_is_a_file_is_a_usage_error(
    runner: CliRunner, prime_fasta: Path
) -> None:
    """A distinct message from the one above, so neither can hide behind the other."""
    result = runner.invoke(app, _design(prime_fasta, "--out", str(prime_fasta / "design.json")))

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    out = _text(result)
    assert "is not a directory" in out, out
    assert "no such directory" not in out, out


def test_an_out_path_in_an_unwritable_directory_is_refused_before_the_run(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """Checked up front because the write happens after the work.

    This is also why `_guarded_write`'s own `OSError` arm (`825`) cannot be reached from
    a shell: this check fires first. That site remains as the backstop for when
    `os.access` is wrong, which its comment says is the point.
    """
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    os.chmod(readonly, 0o500)
    try:
        result = runner.invoke(app, _design(prime_fasta, "--out", str(readonly / "design.json")))
    finally:
        os.chmod(readonly, 0o700)

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    out = _text(result)
    assert "is not writable" in out, out
    assert "because the write happens after it" in out, out


# -- batch, lift and the model registry ----------------------------------------


def test_an_unknown_chemistry_lists_the_real_ones(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    manifest = tmp_path / "cohort.tsv"
    manifest.write_text("variant\nchr2:71:A>C\n")
    result = runner.invoke(
        app, ["batch", str(manifest), "--reference-fasta", str(prime_fasta), "--chemistry", "bogus"]
    )

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    out = _text(result)
    assert "unknown chemistry" in out and "'bogus'" in out, out
    assert "prime" in out, ("the refusal does not list the valid chemistries", out)


def test_a_missing_chain_file_is_missing_data(runner: CliRunner, tmp_path: Path) -> None:
    """`lift` spells its flags `--from` / `--to`, which is why this is written out.

    `--from-build` would be rejected by Typer with exit 2 — numerically equal to
    `ExitCode.USAGE` — and a test asserting only the code would pass while lifting
    nothing.
    """
    result = runner.invoke(
        app,
        [
            "lift",
            "chr2:0-10",
            "--chain",
            str(tmp_path / "absent.chain"),
            "--from",
            "hg19",
            "--to",
            "hg38",
        ],
    )
    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    _assert_one_refusal(result, "chain file not found")


def test_an_unparseable_locus_is_a_usage_error(runner: CliRunner, tmp_path: Path) -> None:
    """Checked before the chain is opened, so the error is about what the caller typed."""
    chain = tmp_path / "x.chain"
    chain.write_text("chain 1 chr2 100 + 0 100 chr2 100 + 0 100 1\n100\n\n")
    result = runner.invoke(
        app, ["lift", "not-a-locus", "--chain", str(chain), "--from", "hg19", "--to", "hg38"]
    )

    assert result.exit_code == ExitCode.USAGE, (result.exit_code, _text(result))
    out = _text(result)
    assert "not-a-locus" in out, out
    assert "chr7:28-48(+)" in out, ("the refusal does not show the expected form", out)


def test_an_unknown_model_name_lists_the_known_ones(runner: CliRunner) -> None:
    result = runner.invoke(app, ["models", "show", "not-a-model"])

    assert result.exit_code == ExitCode.MISSING_DATA, (result.exit_code, _text(result))
    out = _text(result)
    assert "unknown model" in out, out
    assert "be-dict" in out, ("the refusal does not list the registry's names", out)


# -- the invariant -------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["design", "chr2:71:A>C", "--intent", "install", "--reference-fasta", "/nonexistent.fa"],
        ["models", "show", "not-a-model"],
        ["lift", "not-a-locus", "--chain", "/nonexistent.chain", "--from", "hg19", "--to", "hg38"],
        ["resolve", "not-a-variant", "--reference-fasta", "/nonexistent.fa"],
    ],
    ids=["bad-reference", "bad-model", "bad-locus", "bad-variant"],
)
def test_no_reachable_refusal_exits_zero(runner: CliRunner, argv: list[str]) -> None:
    """One weak assertion that would catch any deletion on the paths it covers."""
    result = runner.invoke(app, argv)
    assert result.exit_code != 0, (
        f"`aforge {' '.join(argv)}` refused and still exited 0",
        _text(result),
    )
