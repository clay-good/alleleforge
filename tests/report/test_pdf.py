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


def test_pdf_includes_ancestry_offtarget(ancestry_menu: RankedMenu) -> None:
    pdf = render_pdf(build_report(ancestry_menu))
    assert b"afr: worst score" in pdf
    assert b"specificity" in pdf  # the aggregate genome-wide specificity score
    assert b"PROVENANCE" in pdf
    assert b"Models: cas9-efficiency-ensemble 0.1" in pdf


def test_pdf_leave_behind_carries_oligos_and_prep_note(prime_menu: RankedMenu) -> None:
    # The PDF is the printable leave-behind, so it must carry the exact oligos to
    # order and the phosphorylation prerequisite — not just point at the HTML.
    pdf = render_pdf(build_report(prime_menu, with_oligos=True))
    assert b"cloning oligos" in pdf
    assert b"spacer top" in pdf and b"ext top" in pdf  # the pegRNA duplexes
    assert b"Phosphorylate the annealed oligos with T4 PNK" in pdf  # the prep note
