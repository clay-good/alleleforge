"""The one clause of the search description a caller can act on.

`search_description()` is one sentence carrying the mismatch budget, the reporting
cut-offs, the sub-threshold tail, the PAM broadening, the MAF cut-off and — at the end —
that every supplied population record was for another assembly. Six of those describe what
the scan *did*. The seventh says **you gave it the wrong file**, and it is the only one with
a remedy, sitting at the end of a seven-hundred-character paragraph in neutral text.

`aforge offtarget` already elevates the other actionable clause — the unexcluded on-target
locus — out of the paragraph and onto its headline in brackets. This follows that
precedent, and the page gets the same fact in the hazard style it uses for caveats, above
the paragraph rather than inside it.

Short on purpose: the paragraph keeps the full explanation, and a headline that repeats it
is a headline nobody reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import build_mismatch_note, headline_notes

_SPACER = "ACCTGACTCCTGAGGAGAAG"
_ALT = {"A": "G", "G": "A", "C": "T", "T": "C"}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    random.seed(11)
    seq = list("".join(random.choice("ACGT") for _ in range(4000)))
    seq[1000:1023] = list(_SPACER + "TGG")
    path = tmp_path / "ref.fa"
    body = "".join(seq)
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


def _base(fasta: Path, one_based: int) -> str:
    import pyfaidx

    return str(pyfaidx.Fasta(str(fasta))["chr11"][one_based - 1 : one_based]).upper()


def _report(fasta: Path, tmp_path: Path, *, agreeing: bool) -> object:
    rows = []
    for pos in (1100, 1200):
        base = _base(fasta, pos)
        ref, alt = (base, _ALT[base]) if agreeing else (_ALT[base], base)
        rows.append(f"chr11\t{pos}\t{ref}\t{alt}\t0.02\t0.055\t0.0008")
    path = tmp_path / f"{'right' if agreeing else 'wrong'}.tsv"
    path.write_text("#chrom\tpos\tref\talt\taf\tafr\tnfe\n" + "\n".join(rows) + "\n")
    return search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(path),
        populations=["afr", "nfe"],
    )


def test_every_headline_note_is_also_in_the_paragraph(fasta: Path, tmp_path: Path) -> None:
    """Elevating a fact must not move it, and the two must not drift apart.

    Both are built from the model's own fields — never by parsing the description — so
    this checks the *claim* rather than the mechanism: whatever the headline says short,
    the artifact says long.
    """
    report = _report(fasta, tmp_path, agreeing=False)
    notes = headline_notes(report)  # type: ignore[arg-type]
    assert notes, "the fixture no longer produces a note, so the check below is vacuous"
    description = report.search_description()  # type: ignore[attr-defined]
    for note in notes:
        # The short form is a different sentence; the *subject* has to appear in both.
        subject = note.split(" — ")[0].split(":")[0].split(",")[0]
        assert subject.lower().split()[0] in description.lower(), (note, subject)


def test_a_short_query_is_a_headline_note(fasta: Path) -> None:
    """The clause an earlier round added, which was in the paragraph and nowhere else."""
    report = search("ACGT", PAM(pattern="NGG"), reference=ReferenceGenome(fasta, build="hg38"))
    assert any("not a guide length" in n for n in headline_notes(report))


def test_a_clean_run_has_no_headline_notes(fasta: Path) -> None:
    report = search(_SPACER, PAM(pattern="NGG"), reference=ReferenceGenome(fasta, build="hg38"))
    assert headline_notes(report) == ()


def test_a_wrong_build_source_is_a_headline_note(fasta: Path, tmp_path: Path) -> None:
    note = build_mismatch_note(_report(fasta, tmp_path, agreeing=False))
    assert note == "gnomad: 2 of 2 record(s) are for another build"


def test_it_is_absent_when_the_records_agree(fasta: Path, tmp_path: Path) -> None:
    assert build_mismatch_note(_report(fasta, tmp_path, agreeing=True)) is None


def test_it_is_shorter_than_the_paragraph_it_is_lifted_from(fasta: Path, tmp_path: Path) -> None:
    """A headline that repeats the paragraph is a headline nobody reads."""
    report = _report(fasta, tmp_path, agreeing=False)
    note = build_mismatch_note(report)
    assert note is not None
    assert len(note) < len(report.search_description()) / 4  # type: ignore[attr-defined]


def test_the_paragraph_still_carries_the_full_sentence(fasta: Path, tmp_path: Path) -> None:
    """Elevating a fact must not move it: the description is what travels in artifacts."""
    description = _report(fasta, tmp_path, agreeing=False).search_description()  # type: ignore[attr-defined]
    assert "not an absence of population risk" in description


def test_both_shells_show_them_beside_the_numbers() -> None:
    """The CLI headline and the page's result block, which are the two documents here.

    Both read `headline_notes`, so a note added to that function reaches both without
    anyone remembering — the alternative was two lists, which is how the first version of
    this fix elevated one clause of five.
    """
    from alleleforge.cli import main as cli_main

    source = Path(cli_main.__file__).read_text(encoding="utf-8")
    assert "headline_notes(report)" in source, "the CLI headline does not carry them"

    app_js = (
        Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
    ).read_text(encoding="utf-8")
    assert "data.headline_notes" in app_js, "the page does not carry them"
    index = app_js.index("data.headline_notes")
    assert 'class="err"' in app_js[index : index + 250], "the page renders them as neutral text"


def test_an_unbacked_ancestry_is_a_headline_note(fasta: Path, tmp_path: Path) -> None:
    """Requested, not examined — the other clause with a remedy, and the one the first
    version of this fix left in the paragraph."""
    path = tmp_path / "sites.tsv"
    # One real row: a header-only file carries no ancestry labels at all, which is the
    # *neighbouring* disclosure ("no ancestry source was supplied") and a different note.
    path.write_text(
        f"#chrom\tpos\tref\talt\taf\tafr\nchr11\t1100\t{_base(fasta, 1100)}\tA\t0.02\t0.05\n"
    )
    report = search(
        _SPACER,
        PAM(pattern="NGG"),
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(path),
        populations=["afr", "eas"],
    )
    assert any("not examined for eas" in n for n in headline_notes(report))


def test_a_search_that_examined_nothing_is_a_headline_note() -> None:
    """The most reassuring report the system can produce, from a scan of no bases.

    Constructed rather than run: a reference short enough to search no bases still
    *searches* them. The state is real — a truncated reference, or a region scope that
    resolved to nothing — and it is the one an engine run cannot easily be talked into.
    """
    from alleleforge.types.offtarget import OffTargetReport

    empty = OffTargetReport(
        spacer=_SPACER,
        pam="NGG",
        sites=(),
        mismatch_threshold=4,
        dna_bulge_budget=1,
        rna_bulge_budget=1,
        cfd_threshold=0.0,
        mit_threshold=0.0,
        searched_bases=0,
        resolved_bases=0,
        reference_build="hg38",
        scorer="cfd",
    )
    assert any("NO SEQUENCE WAS SEARCHED" in n for n in headline_notes(empty))


def test_an_ambiguous_spacer_is_a_headline_note(fasta: Path) -> None:
    report = search(
        "ACCTGACTCCTGAGGAGAAN",
        PAM(pattern="NGG"),
        reference=ReferenceGenome(fasta, build="hg38"),
    )
    assert any("ambiguous at position" in n for n in headline_notes(report))


def test_every_kind_of_note_has_a_test() -> None:
    """The population is the function's own branches.

    A mutation deleting two of the five `notes.append` calls left this file green, because
    it exercised the two the round was about. A guard for a *set* has to be checked against
    the set, or it is a guard for the member someone had in mind.
    """
    import ast

    import alleleforge.types.offtarget as module

    source = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(source)
        if isinstance(node, ast.FunctionDef) and node.name == "headline_notes"
    )
    appends = sum(
        1
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
    )
    # Across the package, not this module: the rule is "every kind has a test", and
    # scoping it to one file made it fail the moment a kind was covered next door — which
    # is a guard reporting on where its author happened to be sitting.
    tested = sum(
        len(re.findall(r"^def (test_\w*_headline_note)\(", path.read_text(encoding="utf-8"), re.M))
        for path in Path(__file__).parent.glob("test_*.py")
    )
    assert tested >= appends, (
        f"{appends} kinds of headline note are emitted and {tested} have a test named "
        "`test_..._is_a_headline_note`. A guard for a set checked against one member is "
        "a guard for the member someone had in mind."
    )


@pytest.mark.anyio
async def test_the_endpoint_fills_them(fasta: Path) -> None:
    """Through the endpoint, not by calling the function.

    Every other check here exercises `headline_notes` directly, which says the *function*
    works and nothing about whether the response a client receives carries its output —
    the distinction that let a sibling guard pass while the cohort envelope returned an
    empty list for two rounds.
    """
    pytest.importorskip("fastapi")
    httpx = pytest.importorskip("httpx")

    from alleleforge.web.api.app import create_app

    app = create_app(reference=ReferenceGenome(fasta, build="hg38"))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        short = await client.post("/api/offtarget", json={"spacer": "ACGT"})
        clean = await client.post("/api/offtarget", json={"spacer": _SPACER})
    assert any("not a guide length" in n for n in short.json()["headline_notes"])
    assert clean.json()["headline_notes"] == []
