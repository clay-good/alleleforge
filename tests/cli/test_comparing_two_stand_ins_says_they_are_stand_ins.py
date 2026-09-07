"""The strongest sentence the tool says, over numbers that are not benchmark results.

`aforge bench compare` exists to answer whether two results are the *same scientific
result* — the reproducibility question two labs on two platforms ask each other. On the
bundled fixtures it printed "agree: the same scientific result (timestamps and versions
aside)" and said nothing about the fact that both sides are synthetic stand-ins shipped so
the harness runs in CI.

`bench run` had already been taught to say so, in the round that found the caveat reaching
only the reader who was not keeping the number. `compare` never read the flag at all,
which matters more here for two reasons: this sentence is the one a reader is most likely
to keep as evidence, and this command is the only one that has both sides in hand.

Whether the two agree is unaffected and is still reported; what they agree *about* is now
stated too, on stderr, so it reaches the `--json` caller without entering the data stream.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

runner = CliRunner()


@pytest.fixture
def result(tmp_path: Path) -> Path:
    """A signed result over a bundled (synthetic) fixture."""
    out = tmp_path / "cas9.json"
    run = runner.invoke(app, ["bench", "run", "cas9-efficiency", "--out", str(out)])
    assert run.exit_code == 0, run.output
    return out


@pytest.fixture
def other_result(tmp_path: Path) -> Path:
    out = tmp_path / "pe.json"
    run = runner.invoke(app, ["bench", "run", "pe-efficiency", "--out", str(out)])
    assert run.exit_code == 0, run.output
    return out


def test_agreement_between_stand_ins_says_they_are_stand_ins(result: Path) -> None:
    compared = runner.invoke(app, ["bench", "compare", str(result), str(result)])
    assert compared.exit_code == 0, compared.output
    assert "the same scientific result" in compared.stdout
    assert "SYNTHETIC" in compared.stderr, (
        "two stand-ins were pronounced the same scientific result with no mention that "
        "neither is a benchmark result"
    )
    assert "not agreement about a benchmark result" in compared.stderr


def test_a_disagreement_says_it_too(result: Path, other_result: Path) -> None:
    """The caveat is about the inputs, so it does not depend on the verdict."""
    compared = runner.invoke(app, ["bench", "compare", str(result), str(other_result)])
    assert compared.exit_code != 0, "differing results must still exit non-zero"
    assert "SYNTHETIC" in compared.stderr
    for name in ("rs3-validation", "pridict2-library"):
        assert name in compared.stderr, f"both stand-ins should be named, missing {name}"


def test_the_machine_readable_verdict_carries_it_without_dirtying_stdout(
    result: Path,
) -> None:
    compared = runner.invoke(app, ["bench", "compare", str(result), str(result), "--json"])
    assert compared.exit_code == 0, compared.output
    payload = json.loads(compared.stdout)
    assert payload["agree"] is True
    assert payload["synthetic_datasets"] == ["rs3-validation"], (
        "a caller gating on `agree` must be able to see what it agreed about"
    )
    assert "SYNTHETIC" not in compared.stdout, "the note must stay out of the data stream"
