"""A menu of 2 carried the note "cas9_nuclease: 23 candidate(s)" and no cap anywhere.

`--max-per-chemistry 2` keeps the top two per chemistry. The run notes are written by
each vertical as it finishes, so they report what was *enumerated*; the cap runs after,
during ranking. The result: a rationale asserting 23 above a table of 2, with nothing
saying a cap ran, and a `config_snapshot` that did not record the setting either — so a
re-run from that provenance returns 23.

This is not the render cap. That one keeps every candidate in the export and says so
("the remaining N are in the JSON export"). This one removes them from the result and
from every export of it, so there is no other copy to point a reader at: the only remedy
is to say the number above is not the number below, and what made the difference.

Three more result-determining inputs were missing from the snapshot for the same reason —
they were read at the top of `design()` and never written down: the chemistry restriction
and the two PAM fallbacks, each of which changes what the menu *is*.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import CONFIG_SNAPSHOT_ROUTES
from alleleforge.types.edit import EditIntent


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(7)
    seq = [rng.choice("ACGT") for _ in range(3_000)]
    seq[1000:1023] = list("ACCTGAAGACTTACGCATAC" + "TGG")
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "".join(seq) + "\n")
    return path


def _menu(fasta: Path, cap: int | None) -> object:
    return design(
        "chr1:1018:T>A",
        reference=ReferenceGenome(fasta, build="hg38"),
        run_offtarget=False,
        intent=EditIntent.KNOCK_OUT,
        max_candidates_per_chemistry=cap,
    )


def test_the_fixture_really_gets_capped(fasta: Path) -> None:
    """Without a drop there is nothing to say, and every check below is vacuous."""
    assert len(_menu(fasta, None).candidates) > 2
    assert len(_menu(fasta, 2).candidates) == 2


def test_the_rationale_says_the_counts_above_are_not_the_menu(fasta: Path) -> None:
    menu = _menu(fasta, 2)
    enumerated = len(_menu(fasta, None).candidates)
    assert "max-per-chemistry" in menu.rationale, menu.rationale
    assert str(enumerated - 2) in menu.rationale, menu.rationale
    # And it must say they are gone, not merely elsewhere — the export has 2 as well.
    assert "not in this result or its exports" in menu.rationale


def test_an_uncapped_run_says_nothing_about_a_cap(fasta: Path) -> None:
    """A note that always fires is noise; this one describes something that happened."""
    assert "max-per-chemistry" not in _menu(fasta, None).rationale


def test_a_cap_that_drops_nothing_says_nothing(fasta: Path) -> None:
    """The cap was set and no candidate was removed; there is nothing to warn about."""
    enumerated = len(_menu(fasta, None).candidates)
    assert "max-per-chemistry" not in _menu(fasta, enumerated + 5).rationale


@pytest.mark.parametrize(
    "key", ["chemistries", "max_candidates_per_chemistry", "allow_ng", "allow_spry"]
)
def test_the_result_determining_inputs_are_recorded(fasta: Path, key: str) -> None:
    snapshot = _menu(fasta, 2).provenance.config_snapshot
    assert key in snapshot, sorted(snapshot)


def test_every_recorded_key_still_says_where_it_reaches_a_reader(fasta: Path) -> None:
    """The project's own rule for this dict: a key nobody can see is not provenance."""
    snapshot = _menu(fasta, 2).provenance.config_snapshot
    unrouted = sorted(set(snapshot) - set(CONFIG_SNAPSHOT_ROUTES))
    assert not unrouted, f"snapshot keys with no route to a reader: {unrouted}"


def test_the_cli_records_what_it_was_given(fasta: Path, tmp_path: Path) -> None:
    out = tmp_path / "menu.json"
    result = CliRunner().invoke(
        app,
        [
            "design",
            "chr1:1018:T>A",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "knock_out",
            "--no-offtarget",
            "--max-per-chemistry",
            "2",
            "--allow-ng",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    snapshot = json.loads(out.read_text())["provenance"]["config_snapshot"]
    assert snapshot["max_candidates_per_chemistry"] == 2
    assert snapshot["allow_ng"] is True
    assert snapshot["allow_spry"] is False
