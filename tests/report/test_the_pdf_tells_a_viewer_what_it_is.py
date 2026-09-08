"""A forty-five-page report opened untitled, and was filed as one.

The PDF writer emitted no document information dictionary at all — no `/Title`, no
`/Producer`. That is the field a viewer puts in the window bar and the one a reference
manager files a document under, so a report handed to a colleague arrived nameless, while
the HTML rendering of the same report has carried a `<title>` all along. `pdfinfo` on the
old output printed no Title line; macOS fell back to the filename.

Two things this could only have been checked by opening the file with a real reader.

The title is built from `report.title` rather than a string spelled again here, so the
first page, the HTML `<title>` and the PDF metadata cannot drift apart. And the string is
a PDF *text string* — ASCII literal, or UTF-16BE with a byte-order mark — not the
`WinAnsiEncoding` the page content uses: that encoding belongs to the font the body is
drawn with, and writing the title in it put a `Š` in the middle of the document's own
name where the em dash should be.

No `/CreationDate`: the same report has to render to the same bytes, and a clock in the
metadata would make every run differ from its golden by the one field nobody reads.
"""

from __future__ import annotations

import re

from alleleforge.report.builder import build_report
from alleleforge.report.pdf import render_pdf
from alleleforge.types.candidate import RankedMenu


def _info(pdf: bytes) -> dict[str, str]:
    """Decode the document information dictionary the way a reader does."""
    match = re.search(rb"/Type /Catalog|/Title", pdf)
    assert match, "no information dictionary in the document"
    fields: dict[str, str] = {}
    for key in (b"Title", b"Producer", b"Creator"):
        literal = re.search(rb"/" + key + rb" \(((?:[^()\\]|\\.)*)\)", pdf)
        if literal:
            fields[key.decode()] = literal.group(1).decode("ascii")
            continue
        hexed = re.search(rb"/" + key + rb" <([0-9A-F]+)>", pdf)
        if hexed:
            raw = bytes.fromhex(hexed.group(1).decode("ascii"))
            assert raw.startswith(b"\xfe\xff"), f"{key!r} is hex without a UTF-16 BOM"
            fields[key.decode()] = raw[2:].decode("utf-16-be")
    return fields


def test_the_document_names_itself(prime_menu: RankedMenu) -> None:
    report = build_report(prime_menu, variant="chr2:70:A>C")
    info = _info(render_pdf(report))
    assert report.title in info["Title"], f"the PDF is titled {info.get('Title')!r}"
    assert str(report.variant) in info["Title"], "the title should name the variant"
    assert info["Producer"].startswith("AlleleForge")


def test_a_non_ascii_title_survives_a_reader(prime_menu: RankedMenu) -> None:
    """The em dash between the report name and the variant is the case that broke."""
    info = _info(render_pdf(build_report(prime_menu, variant="chr2:70:A>C")))
    assert "—" in info["Title"], (
        "the em dash was mangled: an information-dictionary string is not written in "
        "the font's WinAnsiEncoding"
    )


def test_the_metadata_carries_no_clock(prime_menu: RankedMenu) -> None:
    """Two renders of one report must be the same bytes."""
    report = build_report(prime_menu)
    assert render_pdf(report) == render_pdf(report)
    assert b"/CreationDate" not in render_pdf(report)


def test_the_page_tree_still_parses_after_the_extra_object(prime_menu: RankedMenu) -> None:
    """Inserting `/Info` renumbered every page object; the xref has to follow."""
    pdf = render_pdf(build_report(prime_menu))
    # `\nxref\n`, not `xref\n`: `startxref\n` ends with the shorter needle and comes
    # later in the file, so the naive search lands on the pointer rather than the table.
    start = pdf.rindex(b"\nxref\n") + 1
    header, _, rest = pdf[start:].partition(b"\n")
    counts, _, table = rest.partition(b"\n")
    total = int(counts.split()[1])
    entries = re.findall(rb"(\d{10}) \d{5} ([nf]) ", table)
    assert len(entries) >= total - 1, f"xref lists {len(entries)} of {total} objects"
    for number, (offset, kind) in enumerate(entries):
        if kind != b"n":
            continue
        assert pdf[int(offset) :].startswith(f"{number} 0 obj".encode()), (
            f"xref entry {number} points at {pdf[int(offset) : int(offset) + 16]!r}"
        )
