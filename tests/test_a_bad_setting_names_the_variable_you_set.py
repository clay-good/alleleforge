"""A mistyped environment variable arrived as a pydantic traceback naming a field.

`Settings` derives its variable names from `env_prefix`, so an operator sets
`ALLELEFORGE_SEED` and pydantic reports `seed`. The one string a reader could search for —
the one in the deployment guide's settings table — was the one string the error did not
print, and the rest of it was a stack trace through pydantic-settings.

Where that lands makes it worse. `alleleforge.web.api.app` builds its app at module scope,
so a mistyped variable is not a bad request but a container that will not start, and this
message is the whole diagnosis available in the log. On the command line it exited `1`, the
code this CLI reserves for a defect in itself, for a mistake in the caller's environment.

Deliberately still fatal. A seed or an interval level has no honest degraded mode:
substituting the default would stamp every result with a number the operator did not
choose, and this project's reproducibility claims rest on that number. Failing to start is
right; failing to start with a stack trace is not. (A *path* is different — a missing
reference is recorded and the service answers "no genome, here is why".)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from alleleforge.config import Settings

_ROOT = Path(__file__).resolve().parents[1]

#: One malformed value per validation kind: unparseable, and out of range.
_BAD = [
    ("ALLELEFORGE_SEED", "notanumber", "valid integer"),
    ("ALLELEFORGE_MAF_THRESHOLD", "abc", "valid number"),
    ("ALLELEFORGE_INTERVAL_LEVEL", "99", "less than or equal"),
]


@pytest.mark.parametrize(("variable", "value", "reason"), _BAD)
def test_the_message_names_the_variable_not_the_field(
    variable: str, value: str, reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError) as excinfo:
        Settings.load()
    message = str(excinfo.value)
    assert variable in message, message
    assert repr(value) in message, message
    assert reason in message, message
    # And it points at where the settings are documented, since the name alone does not
    # say what the accepted values are.
    assert "docs/deployment.md" in message, message


def test_a_good_environment_still_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard the guard: the wrapper must not turn every load into an error."""
    monkeypatch.setenv("ALLELEFORGE_SEED", "1234")
    assert Settings.load().seed == 1234


@pytest.mark.parametrize(("variable", "value", "reason"), _BAD)
def test_the_cli_reports_it_as_a_usage_error(
    variable: str, value: str, reason: str, tmp_path: Path
) -> None:
    """Exit 2, not 1: it is the caller's environment, not a defect in this tool.

    With a real reference, because `design` loads one before it loads settings — the
    first draft of this test omitted it and measured the missing-reference exit instead.
    """
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "ACGTTGCAAGGCTTACCGTA" * 20 + "\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alleleforge.cli.main",
            "design",
            "chr1:103:G>A",
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": "/usr/bin:/bin", variable: value},
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "Traceback" not in output, output
    assert variable in output, output


@pytest.mark.parametrize(("variable", "value", "reason"), _BAD)
def test_the_web_app_says_which_variable_rather_than_which_field(
    variable: str, value: str, reason: str
) -> None:
    """The app is built at import, so this message is the entire container log."""
    result = subprocess.run(
        [sys.executable, "-c", "import alleleforge.web.api.app"],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": "/usr/bin:/bin", variable: value},
    )
    assert result.returncode != 0
    assert variable in result.stderr, result.stderr
    assert "validation error for Settings" not in result.stderr, result.stderr


def _design(tmp_path: Path, *argv: str, **env: str) -> dict[str, object]:
    """Run `aforge design` and return the parsed menu."""
    import json

    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "ACGTTGCAAGGCTTACCGTA" * 20 + "\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alleleforge.cli.main",
            *argv,
            "design",
            "chr1:103:G>A",
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": "/usr/bin:/bin", **env},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_the_documented_seed_variable_actually_changes_the_run(tmp_path: Path) -> None:
    """`ALLELEFORGE_SEED` did nothing on the command line, and was documented as a setting.

    The `--seed` option carried `DEFAULT_SEED` as its default and that default was passed
    to `Settings.load` as an *override*. Overrides outrank the environment — correctly,
    for a value the caller actually typed — so the variable listed in the deployment
    guide changed nothing on any CLI run, while the library honoured it. Every design
    stamped 20240501 into its provenance whatever the operator set.

    A flag's default is not something the caller said.
    """
    assert _design(tmp_path)["provenance"]["seed"] == 20240501
    assert _design(tmp_path, ALLELEFORGE_SEED="1234")["provenance"]["seed"] == 1234


def test_an_explicit_flag_still_outranks_the_environment(tmp_path: Path) -> None:
    """The precedence the docs state: defaults < file < environment < explicit override."""
    menu = _design(tmp_path, "--seed", "999", ALLELEFORGE_SEED="1234")
    assert menu["provenance"]["seed"] == 999
    assert _design(tmp_path, "--seed", "999")["provenance"]["seed"] == 999


def _resolve(*argv: str, **env: str) -> dict[str, object]:
    """Run `aforge resolve` and return the parsed payload."""
    import json

    result = subprocess.run(
        [sys.executable, "-m", "alleleforge.cli.main", *argv, "resolve", "chr1:5:A>T", "--json"],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": "/usr/bin:/bin", **env},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_the_documented_reference_variable_actually_changes_the_run() -> None:
    """The sibling of the seed defect, on the option that sets the coordinate frame.

    `--reference` carried `hg38` as its default and that default reached every consumer
    directly, so `ALLELEFORGE_REFERENCE` — honoured by the library, listed in the
    deployment guide — changed nothing on any CLI run. The build label is stamped into
    provenance and decides which assembly a locus is reported against, so this is the
    same mechanism with a larger blast radius than the seed's.
    """
    assert _resolve()["build"] == "hg38"
    assert _resolve(ALLELEFORGE_REFERENCE="mm39")["build"] == "mm39"


def test_an_explicit_reference_flag_still_outranks_the_environment() -> None:
    assert _resolve("--reference", "T2T-CHM13v2")["build"] == "T2T-CHM13v2"
    assert _resolve("--reference", "hg38", ALLELEFORGE_REFERENCE="mm39")["build"] == "hg38"
