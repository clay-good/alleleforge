"""A whole chemistry can drop out of a menu and the command still exited 0.

When a chemistry's vertical raises an *unexpected* exception, `_run_chemistry` records it
as a defect note and returns no candidates rather than crashing the design. That graceful
degradation is deliberate and the rationale says so where a reader looks:

    prime: ERROR — unexpected CacheIntegrityError: … (a defect, not 'no design')

Reporting *success* for it is not part of it. `aforge batch` already draws this line — "a
script or a CI job driving this had no way to tell without re-parsing the summary, while
`verify`, `bench compare` and `scripts/reproduce.py` all signal failure through the exit
code" — and `design` did not. The case that surfaced it: a corrupted `--cache` entry,
refused rather than served, took the prime vertical out of a menu, and the command wrote a
zero-candidate report and exited 0.

The menu is still written. The run happened, the rationale explains it, and throwing the
output away would help nobody; only the exit code changes.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.design import designer


@pytest.fixture
def reference(tmp_path: Path) -> Path:
    rng = random.Random(7)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(20000)) + "\n")
    return fasta


def _variant(reference: Path) -> str:
    sequence = "".join(reference.read_text().split("\n")[1:])
    base = sequence[9999]
    return f"chr1:10000:{base}>{'A' if base != 'A' else 'G'}"


def test_a_defect_note_is_the_marker_the_shell_reads() -> None:
    """The seam: the note is prose, so rewording it must not un-fail the command."""
    notes: list[str] = []

    def boom() -> list[object]:
        raise RuntimeError("something nobody expected")

    result = designer._run_chemistry("prime", boom, notes)  # type: ignore[arg-type]
    assert result == []
    assert len(notes) == 1, notes
    assert designer.DEFECT_NOTE in notes[0], notes[0]


def test_the_command_fails_when_a_chemistry_hit_a_defect(
    reference: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And still writes the menu: the run happened and its rationale explains itself."""

    def boom(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("the vertical is broken")

    # Patched on `designer`, which imported the name: patching the defining module would
    # leave this binding untouched and the test would pass on unbroken code.
    monkeypatch.setattr(designer, "design_prime", boom)

    out = tmp_path / "menu.json"
    result = CliRunner().invoke(
        app,
        [
            "design",
            _variant(reference),
            "--reference-fasta",
            str(reference),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == ExitCode.UNAVAILABLE, result.output + result.stderr
    assert "unexpected error" in result.stderr, result.stderr

    report = json.loads(out.read_text())
    assert designer.DEFECT_NOTE in report["rationale"], report["rationale"]


def test_an_ordinary_run_still_exits_zero(reference: Path, tmp_path: Path) -> None:
    """The check must not turn every empty or partial menu into a failure."""
    out = tmp_path / "menu.json"
    result = CliRunner().invoke(
        app,
        [
            "design",
            _variant(reference),
            "--reference-fasta",
            str(reference),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    assert designer.DEFECT_NOTE not in json.loads(out.read_text())["rationale"]
