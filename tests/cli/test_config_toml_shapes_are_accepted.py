"""A run-config TOML written as TOML must not crash the command.

`weights` is on `_RUN_PARAM_KEYS`, so `_load_config` accepts it without a typo
warning and hands it to `_parse_weights`, which only ever handled the CLI's
`"eff,clean,safe,simple"` string. Both natural TOML spellings therefore reached an
uncaught exception:

    weights = [0.35, 0.3, 0.3, 0.05]   ->  AttributeError: 'list' has no 'split'
    [weights]                          ->  AttributeError: 'dict' has no 'split'
    efficiency = 0.35 ...

The table form is not hypothetical. It is exactly the shape a result's own
`provenance.config_snapshot` records the weights in, so a user reconstructing a run
from its provenance — the thing provenance exists for — writes the spelling that
crashes.

`populations` had the identical defect one key over — the flag takes `afr,eur` and a
TOML file writes `["afr", "eur"]`, which reached the same `str.split`. The class is
every whitelisted config key whose flag is a comma-separated string, so both are fixed
and the documented example is executed here rather than proofread.

A traceback is a missing decision (R115). The decision here is that a config file is
TOML and should be written as TOML: a table keyed by the four axis names, or a
four-element array in the documented order. All three spellings must agree, and a
malformed one must be a usage error naming what was expected.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.design.ranking import RankingWeights

_SPEC = RankingWeights(efficiency=0.4, cleanliness=0.3, safety=0.2, simplicity=0.1)


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


def _run(runner: CliRunner, fasta: Path, tmp_path: Path, extra: list[str]) -> dict[str, object]:
    out = tmp_path / "menu.json"
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
            "--out",
            str(out),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return dict(json.loads(out.read_text()))


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("weights = [0.4, 0.3, 0.2, 0.1]\n", id="array"),
        pytest.param(
            "[weights]\nefficiency = 0.4\ncleanliness = 0.3\nsafety = 0.2\nsimplicity = 0.1\n",
            id="table",
        ),
        pytest.param('weights = "0.4,0.3,0.2,0.1"\n', id="string"),
    ],
)
def test_every_spelling_of_weights_produces_the_same_run(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path, body: str
) -> None:
    """Array, table and string are the same weights, and none of them crashes."""
    cfg = tmp_path / "run.toml"
    cfg.write_text(body)
    from_config = _run(runner, prime_fasta, tmp_path, ["--config", str(cfg)])
    from_flag = _run(runner, prime_fasta, tmp_path, ["--weights", "0.4,0.3,0.2,0.1"])

    recorded = from_config["provenance"]["config_snapshot"]["weights"]  # type: ignore[index]
    # Recorded weights are the normalized ones, so compare within float noise.
    assert recorded == pytest.approx(dataclasses.asdict(_SPEC))
    assert from_config["candidates"] == from_flag["candidates"]


def test_the_recorded_snapshot_is_itself_an_accepted_spelling(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """What provenance writes for `weights` must be what `--config` reads back."""
    first = _run(runner, prime_fasta, tmp_path, ["--weights", "0.4,0.3,0.2,0.1"])
    recorded = first["provenance"]["config_snapshot"]["weights"]  # type: ignore[index]
    assert isinstance(recorded, dict)

    cfg = tmp_path / "round.toml"
    cfg.write_text("[weights]\n" + "".join(f"{k} = {v}\n" for k, v in recorded.items()))
    again = _run(runner, prime_fasta, tmp_path, ["--config", str(cfg)])
    assert again["candidates"] == first["candidates"]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("weights = [0.4, 0.3]\n", id="short-array"),
        pytest.param("[weights]\nefficiency = 0.4\n", id="incomplete-table"),
        pytest.param("[weights]\nefficiency = 0.4\nbogus = 0.3\n", id="unknown-axis"),
        pytest.param("weights = 0.4\n", id="scalar"),
        pytest.param("weights = [0.0, 0.0, 0.0, 0.0]\n", id="all-zero"),
    ],
)
def test_a_malformed_weights_key_is_a_usage_error_not_a_traceback(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path, body: str
) -> None:
    cfg = tmp_path / "run.toml"
    cfg.write_text(body)
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--config",
            str(cfg),
            "--no-offtarget",
        ],
    )
    assert result.exit_code == ExitCode.USAGE, result.output
    combined = result.output + result.stderr
    assert "weights" in combined
    assert "Traceback" not in combined


def test_populations_as_a_toml_array_is_accepted(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """The array form must reach the search, and still raise the reference-only warning."""
    cfg = tmp_path / "pops.toml"
    cfg.write_text('populations = ["afr", "eur"]\n')
    out = tmp_path / "menu.json"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "1",
            "--config",
            str(cfg),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    # The labels reached the honesty check, which is the only observable proof they
    # were parsed rather than dropped: reference-only ancestry is "not measured".
    assert "REFERENCE-ONLY" in result.stderr


def test_the_documented_config_example_runs(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """The TOML block in `docs/api/cli.md` is executed, not proofread.

    That block was written with this change and every key in it crashed the command
    before it: `populations` as an array, and `weights` as a table.
    """
    doc = Path(__file__).resolve().parents[2] / "docs" / "api" / "cli.md"
    text = doc.read_text()
    start = text.index("### The run-config file")
    fence = text.index("```toml", start) + len("```toml")
    body = text[fence : text.index("```", fence)]
    assert "[weights]" in body and "populations" in body, body

    cfg = tmp_path / "documented.toml"
    cfg.write_text(body)
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--out",
            str(tmp_path / "menu.json"),
            "--config",
            str(cfg),
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "unknown config key" not in result.stderr
