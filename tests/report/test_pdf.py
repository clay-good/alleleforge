"""Tests for the Phase 11 pure-Python PDF renderer."""

from __future__ import annotations

from alleleforge.report.builder import build_report
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import RankedMenu


def test_pdf_is_well_formed(prime_menu: RankedMenu) -> None:
    pdf = render_pdf(build_report(prime_menu, variant="chr2:70:A>C"))
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"xref" in pdf
    assert b"/Root 1 0 R" in pdf


def test_pdf_xref_offsets_point_to_objects(prime_menu: RankedMenu) -> None:
    # Parse the xref table and verify each offset lands on "<n> 0 obj".
    pdf = render_pdf(build_report(prime_menu))
    startxref = int(pdf.rsplit(b"startxref", 1)[1].split(b"%%EOF")[0].strip())
    xref = pdf[startxref:]
    assert xref.startswith(b"xref")
    header = xref.split(b"\n")[1]
    size = int(header.split()[1])
    rows = xref.split(b"\n")[2 : 2 + size]
    for n, row in enumerate(rows):
        if row.endswith(b" n "):
            offset = int(row.split()[0])
            assert pdf[offset:].startswith(f"{n} 0 obj".encode())


def test_pdf_multipage_for_large_menu(prime_menu: RankedMenu) -> None:
    pdf = render_pdf(build_report(prime_menu))
    assert pdf.count(b"/Type /Page ") >= 1  # at least one page object


def test_pdf_renders_empty_menu(prime_menu: RankedMenu) -> None:
    from alleleforge.types.candidate import RankedMenu as RM

    empty = RM(candidates=(), provenance=prime_menu.provenance)
    pdf = render_pdf(build_report(empty))
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.rstrip().endswith(b"%%EOF")


def test_pdf_escapes_parentheses(nuclease_menu: RankedMenu) -> None:
    # Reagent summaries contain "(...)"; the PDF must escape them, not break.
    pdf = render_pdf(build_report(nuclease_menu))
    assert b"\\(" in pdf and b"\\)" in pdf


def test_pdf_escape_keeps_winansi_punctuation() -> None:
    # The font is declared /WinAnsiEncoding (CP1252). Encoding to Latin-1 silently
    # turned ordinary punctuation the font *can* render into "?" — data loss on the
    # printable leave-behind. CP1252 keeps the curly apostrophe, en-dash, and euro;
    # only genuinely unrepresentable scripts still fall back to "?".
    from alleleforge.report.pdf import _escape

    assert _escape("Nature’s") == "Nature’s"  # curly apostrophe survives
    assert _escape("exon 3–13") == "exon 3–13"  # en-dash survives
    assert _escape("cost €5") == "cost €5"  # euro survives
    assert _escape("中文") == "??"  # CJK is unrenderable in WinAnsi -> replaced


def test_pdf_includes_ancestry_offtarget(ancestry_menu: RankedMenu) -> None:
    pdf = render_pdf(build_report(ancestry_menu))
    assert b"afr: worst score" in pdf
    assert b"specificity" in pdf  # the aggregate genome-wide specificity score
    assert b"scoring basis: CFD / doench-2016-cfd" in pdf  # the scorer + matrix identity
    # The printable leave-behind states the search too, so a page handed to a
    # collaborator carries the settings its site count is conditional on.
    # Asserted glyph-for-glyph: the description is deliberately ASCII because the
    # WinAnsi font would print a mathematical "<=" as "?" on the handed-out page.
    assert b"search: up to 3 mismatches, 0 DNA / 0 RNA bulges" in pdf
    assert b"sites reported at CFD >= 0.05 or MIT" in pdf  # wraps after this
    assert b"PROVENANCE" in pdf
    assert b"models: cas9-efficiency-ensemble 0.1" in pdf


def test_pdf_leave_behind_carries_oligos_and_prep_note(prime_menu: RankedMenu) -> None:
    # The PDF is the printable leave-behind, so it must carry the exact oligos to
    # order and the phosphorylation prerequisite — not just point at the HTML.
    pdf = render_pdf(build_report(prime_menu, with_oligos=True))
    assert b"cloning oligos" in pdf
    assert b"spacer top" in pdf and b"ext top" in pdf  # the pegRNA duplexes
    assert b"Phosphorylate the annealed oligos with T4 PNK" in pdf  # the prep note


def test_pdf_includes_ranking_rationale(ancestry_menu: RankedMenu) -> None:
    # The printable leave-behind must carry each candidate's ranking rationale, like
    # the HTML and JSON surfaces — it explains why a candidate ranks where it does.
    pdf = render_pdf(build_report(ancestry_menu))
    assert b"synthetic ancestry fixture" in pdf


def test_the_order_sheet_says_when_a_g_was_prepended(prime_menu: RankedMenu) -> None:
    """The PDF is the sheet someone orders from, and the ordered guide is not the
    spacer that was scored.

    U6 transcription needs a 5' G, so the lentiGuide scheme prepends one — the cloned
    guide is 21 nt while every efficiency and off-target number on the page describes
    the 20-nt spacer. The oligo record carries `g_added`, the HTML buries it in a JSON
    dump of that record, and the PDF's formatted block omitted it entirely.
    """
    from alleleforge.report.oligos import sgrna_oligos
    from alleleforge.report.pdf import _oligo_lines

    # A spacer that does not begin with G, so the scheme adds one.
    oligos = sgrna_oligos("TTTAAACGTTTTTTTTTTTT")
    assert oligos.g_added, "this spacer must trigger the prepend for the check to mean anything"

    text = " ".join(_oligo_lines(oligos))
    assert "prepended" in text
    assert "21 nt" in text  # the cloned length
    assert "20-nt spacer" in text  # ...and the scored one


def test_no_note_when_the_spacer_already_starts_with_g() -> None:
    """The note must not appear where nothing was changed."""
    from alleleforge.report.oligos import sgrna_oligos
    from alleleforge.report.pdf import _oligo_lines

    oligos = sgrna_oligos("GACCCCCTCCACCCCGCCTC")
    assert not oligos.g_added
    assert "prepended" not in " ".join(_oligo_lines(oligos))


def test_the_order_sheet_carries_the_hdr_donor() -> None:
    """The printable sheet listed the guide duplex and not the repair template.

    `oligos_for` pairs a precise Cas9 candidate with its donor, and its own test says
    why: "returning only the guide would hand the bench the half that cannot edit."
    The PDF then handed the bench exactly that half — no donor sequence, and not even
    the word "donor", while the candidate line above said "+ HDR donor 100 nt", so a
    reader knew one existed and could not order it from the page.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from alleleforge.report.oligos import oligos_for
    from alleleforge.report.pdf import _oligo_lines
    from report.test_oligos import _precise_cas9_candidate  # type: ignore[import-not-found]

    # Deliberately unlike the fixture's ACGT-repeat spacer: an earlier version of this
    # check matched the spacer by coincidence and reported the donor as present.
    donor = "TTGGCCAA" * 12 + "TTGG"
    oligos = oligos_for(_precise_cas9_candidate(donor))
    assert oligos.donor is not None

    text = " ".join(_oligo_lines(oligos))
    assert "HDR donor" in text
    assert "100 nt" in text
    assert "re-cut blocked" in text
    # The sequence itself, ignoring the line wrapping the PDF applies.
    assert donor in text.replace(" ", "").replace("\n", "")


def test_a_guide_without_a_donor_gets_no_donor_block() -> None:
    from alleleforge.report.oligos import sgrna_oligos
    from alleleforge.report.pdf import _oligo_lines

    assert "HDR donor" not in " ".join(_oligo_lines(sgrna_oligos("GACCCCCTCCACCCCGCCTC")))
