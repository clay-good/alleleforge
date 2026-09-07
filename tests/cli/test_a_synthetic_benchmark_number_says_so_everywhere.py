"""The caveat reached the reader who runs it and not the two who keep the number.

The bundled benchmark fixtures are synthetic stand-ins, shipped so the harness runs in
CI, and a Spearman over ten synthetic rows prints in exactly the shape of one over
GUIDE-seq. An earlier round fixed that by printing a NOTE beside the number — in the
branch that runs when neither `--out` nor `--json` was given.

So the user who types `aforge bench run cas9-efficiency` was told. The user who wrote it
to a file saw "wrote result.json" and nothing else, and the user who piped the JSON got
`dataset_is_synthetic` — which is the same field the round's own comment says "nothing
read". Those two are the ones who keep, share and publish the number. This is the
project's reputational guardrail, on the surface it exists for.

The note belongs on stderr, where this CLI puts every message about a side effect: it
then reaches all three modes without putting a sentence in a pipeline's data stream.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from alleleforge.cli.main import app

runner = CliRunner()

_TASK = "cas9-efficiency"
_MARKER = "SYNTHETIC"


def _run(*extra: str) -> tuple[str, str]:
    result = runner.invoke(app, ["bench", "run", _TASK, *extra])
    assert result.exit_code == 0, result.output
    return result.stdout, result.stderr


def test_the_bare_run_still_says_so() -> None:
    stdout, stderr = _run()
    assert _MARKER in stdout + stderr


def test_saving_the_result_says_so(tmp_path: Path) -> None:
    """The user who keeps the number is the one who most needs the caveat."""
    stdout, stderr = _run("--out", str(tmp_path / "r.json"))
    assert _MARKER in stderr, (
        "writing the result to a file reported only the path; the reader who saves a "
        "synthetic number was never told it is not a benchmark result"
    )


def test_piping_the_result_says_so_without_dirtying_stdout(tmp_path: Path) -> None:
    stdout, stderr = _run("--json")
    assert _MARKER in stderr, "the JSON path never warned a human at all"
    json.loads(stdout), "stdout must stay a clean data stream a pipeline can parse"
    assert _MARKER not in stdout, "the caveat must not be printed into the data stream"


def test_the_saved_result_still_carries_the_flag(tmp_path: Path) -> None:
    """The terminal note is the addition, not a replacement for the in-band field."""
    out = tmp_path / "r.json"
    _run("--out", str(out))
    assert json.loads(out.read_text(encoding="utf-8"))["dataset_is_synthetic"] is True
