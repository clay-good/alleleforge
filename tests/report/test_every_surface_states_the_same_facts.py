"""Whole-document facts must appear on every render of a report.

The previous round found the TSV emitting none of the disclaimer, the coordinate
convention or the provenance footer while the HTML, PDF and JSON emitted all three,
and its lesson was that "which renderer is missing this?" needs asking on a schedule
rather than once. This is that check, made durable.

Building the table found the remaining gap immediately: `report_to_json` — the
machine-readable export a pipeline consumes — states **no coordinate convention at
all**. Its `locus` is a formatted string (`chr2:43-63 (+), nick 60`), and the
`Provenance` model it embeds has no coordinate note, because that note lives in
`provenance_lines()`, a render helper the JSON never calls. Every locus in the
document is 0-based half-open and a genome browser reads the same digits as 1-based
inclusive, which is the confusion the note exists to prevent.

The omission list is the mechanism: a fact a surface genuinely should not carry has to
be named here with a reason, so a future gap is a failing test rather than a silence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report import (
    build_report,
    render_html,
    render_pdf,
    report_to_json,
    report_to_tsv,
)
from alleleforge.types.edit import EditIntent

#: One needle per fact. Each is a whole-document statement, not a per-candidate one:
#: a reader who has the table but not these cannot interpret any row in it.
#: `reference identity` is keyed off the run's own digest rather than a literal,
#: because the prose renders print its first eight characters and the JSON carries
#: the whole hash — the same fact in two encodings.
FACTS: dict[str, str | None] = {
    "research-use disclaimer": "not a medical device",
    "coordinate convention": "0-based",
    "reference identity": None,  # filled from the report; see `surfaces`
    "reference build": "hg38",
    "seed": "20240501",
    "model identity": "pridict2-baseline",
}

#: `(fact, surface)` pairs a render legitimately omits, each with the reason. Empty
#: is the goal; an entry is a decision, and one without a reason is not allowed.
OMITTED: dict[tuple[str, str], str] = {}

#: Formats `aforge design --format` offers that this file does not render, with the
#: reason. The population is the enum, not a list written here: this guard covered four
#: surfaces for several rounds while the CLI offered six, and the fifth — Parquet — is a
#: *flat table*, exactly the surface whose missing facts started this file.
NOT_A_REPORT_RENDER: dict[str, str] = {
    "menu": "a different document: the ranked menu, not the report. It carries the full "
    "candidate list the report truncates, and its own facts are checked by the menu "
    "tests",
}


@pytest.fixture(scope="module")
def surfaces(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Render one report through every surface, as text."""
    tmp_path: Path = tmp_path_factory.mktemp("surfaces")
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    report = build_report(
        design(
            "chr2:71:A>C",
            reference=ReferenceGenome(fasta, build="hg38"),
            intent=EditIntent.INSTALL,
            max_candidates_per_chemistry=1,
        )
    )
    assert report.provenance is not None
    shape = report.provenance.config_snapshot["reference"]
    assert isinstance(shape, dict)
    FACTS["reference identity"] = str(shape["sha256"])[:8]
    return {
        "html": render_html(report),
        "tsv": report_to_tsv(report),
        "json": report_to_json(report),
        # The PDF's content stream is uncompressed text; a fact wrapped across a
        # line is still present, so the needles are short enough to survive that.
        "pdf": render_pdf(report).decode("latin-1", "replace"),
        # Parquet holds no comment lines, so its facts live in the file-level key/value
        # metadata — the same notes the TSV writes as `#` lines. Read back as one string,
        # because what is being asked is whether the fact is *in the file*.
        "parquet": _parquet_notes(report, tmp_path / "report.parquet"),
    }


def _parquet_notes(report: object, path: Path) -> str:
    """Return the file-level metadata of the Parquet export, as one searchable string."""
    import polars as pl

    from alleleforge.report import report_to_parquet

    written = report_to_parquet(report, path)  # type: ignore[arg-type]
    metadata = pl.read_parquet_metadata(written)
    return "\n".join(f"{key}: {value}" for key, value in sorted(metadata.items()))


@pytest.mark.parametrize("fact", sorted(FACTS))
@pytest.mark.parametrize("surface", ["html", "tsv", "json", "pdf", "parquet"])
def test_the_fact_is_on_the_surface(surfaces: dict[str, str], fact: str, surface: str) -> None:
    needle = FACTS[fact]
    assert needle, f"{fact!r} has no needle; the fixture must fill it in"
    reason = OMITTED.get((fact, surface))
    present = needle in surfaces[surface]
    if reason:
        assert not present, (
            f"{surface} now carries the {fact!r} it is listed as omitting — remove the "
            f"entry from OMITTED (its reason was: {reason})"
        )
        return
    assert present, (
        f"the {surface} render omits the {fact!r} that every other render carries. "
        "Add it where the surface states its whole-document context, or record the "
        "omission in OMITTED with the reason a reader needs."
    )


def test_the_json_names_its_coordinate_system_as_data(surfaces: dict[str, str]) -> None:
    """A machine consumer must not have to grep prose for the convention."""
    payload = json.loads(surfaces["json"])
    assert payload["coordinate_system"] == "0-based-half-open"


def test_the_needles_are_not_vacuous(surfaces: dict[str, str]) -> None:
    """Guard the guard: a needle that matches everything proves nothing."""
    for surface, text in surfaces.items():
        assert len(text) > 500, surface
    assert "not a medical device" not in "chr2:43-63 (+), nick 60"


def test_the_two_spellings_agree() -> None:
    """The slug and the sentence are one convention; they must not drift apart."""
    from alleleforge.report.builder import COORDINATE_NOTE, COORDINATE_SYSTEM

    assert COORDINATE_SYSTEM.replace("-", " ") in COORDINATE_NOTE.replace("-", " ")


def test_every_format_the_cli_offers_is_rendered_here_or_excused() -> None:
    """The population is `--format`'s own enum, not the list this file happens to render.

    Four surfaces were checked while six were offered, and the unchecked one that mattered
    was Parquet: a flat table, which is the shape whose missing facts this file was written
    about in the first place. Its facts live in file-level metadata rather than in `#`
    comment lines, which is exactly how a surface goes unnoticed — it carries them in a
    place a text search over the document would not look.
    """
    from alleleforge.cli.main import OutputFormat

    offered = {fmt.value for fmt in OutputFormat}
    rendered = {"html", "tsv", "json", "pdf", "parquet"}
    unchecked = sorted(offered - rendered - set(NOT_A_REPORT_RENDER))
    assert not unchecked, (
        f"`aforge design --format` offers {unchecked}, which no surface here renders. "
        "Add it above, or record it in NOT_A_REPORT_RENDER with the reason it is not a "
        "rendering of this report."
    )
    stale = sorted(set(NOT_A_REPORT_RENDER) - offered)
    assert not stale, f"NOT_A_REPORT_RENDER names formats the CLI no longer offers: {stale}"
