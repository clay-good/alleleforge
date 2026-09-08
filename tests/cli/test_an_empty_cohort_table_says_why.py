"""A resumed cohort wrote a table with no rows and no reason.

`aforge batch --manifest m.jsonl --summary-tsv out.tsv` run a second time skips every item
it has already designed — correctly, that is what resume is for — and wrote a well-formed
TSV with seven `#` notes, a column header, and nothing else. A file with no rows reads as a
cohort that produced no results, and nothing in it said otherwise.

The terminal line had already been fixed for exactly this: its comment reads "Stating the
requested count first stops `0 item(s)` from being the headline for a resume that had
nothing left to do — the two numbers now visibly add up." That fix went to the sentence
that scrolls past. The file is the half that outlives the terminal, gets forwarded, and is
opened by someone who did not run the command.

The note is unconditional — a fresh run says what it did too — because a count that only
appears when something went unusually is a count a reader learns to distrust.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app

runner = CliRunner()


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    seq = list("ACGT" * 500)
    for pos in (100, 300, 500):
        seq[pos] = "A"
    path = tmp_path / "ref.fa"
    path.write_text(">chr1\n" + "".join(seq) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def listing(tmp_path: Path) -> Path:
    path = tmp_path / "cohort.txt"
    path.write_text(
        "\n".join(f"chr1:{p + 1}:A>G" for p in (100, 300, 500)) + "\n", encoding="utf-8"
    )
    return path


def _batch(fasta: Path, listing: Path, manifest: Path, out: Path) -> str:
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(fasta),
            "--manifest",
            str(manifest),
            "--summary-tsv",
            str(out),
            "--no-offtarget",
        ],
    )
    assert result.exit_code == 0, result.output + result.stderr
    return out.read_text(encoding="utf-8")


def test_a_resumed_run_says_why_its_table_is_empty(
    fasta: Path, listing: Path, tmp_path: Path
) -> None:
    manifest = tmp_path / "m.jsonl"
    first = _batch(fasta, listing, manifest, tmp_path / "a1.tsv")
    second = _batch(fasta, listing, manifest, tmp_path / "a2.tsv")

    rows = [line for line in second.splitlines() if not line.startswith("#")]
    assert len(rows) == 1, "the resumed run should have written the header and no rows"

    notes = [line for line in second.splitlines() if line.startswith("#")]
    counted = [n for n in notes if "requested" in n]
    assert counted, f"no count note in the resumed table: {notes}"
    assert "3 already done (resume)" in counted[0], counted[0]
    assert "empty because the run had nothing left to design" in counted[0], counted[0]

    # And the first run, which did the work, states what it did rather than staying silent.
    first_counted = [n for n in first.splitlines() if n.startswith("#") and "requested" in n]
    assert first_counted and "3 designed" in first_counted[0], first_counted
    assert "empty because" not in first_counted[0], "a full table must not claim emptiness"


def test_the_numbers_add_up(fasta: Path, listing: Path, tmp_path: Path) -> None:
    """`requested = designed + skipped` — the property the terminal fix was about."""
    manifest = tmp_path / "m.jsonl"
    _batch(fasta, listing, manifest, tmp_path / "b1.tsv")
    text = _batch(fasta, listing, manifest, tmp_path / "b2.tsv")
    note = next(n for n in text.splitlines() if n.startswith("#") and "requested" in n)
    import re

    requested, designed, skipped = (
        int(re.search(rf"(\d+) {word}", note).group(1))  # type: ignore[union-attr]
        for word in ("requested", "designed", "already done")
    )
    assert requested == designed + skipped, note
