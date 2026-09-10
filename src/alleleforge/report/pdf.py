"""Render a design report as a static, print-ready PDF — no dependencies.

A full PDF toolchain (weasyprint, reportlab) is heavy and platform-fragile, so
this module ships a small, self-contained writer that emits a valid multi-page
PDF 1.4 with Helvetica text. It is deliberately text-and-table oriented: the
interactive charts live in the HTML render ([`render_html`][alleleforge.report.html.render_html]);
the PDF is the leave-behind that prints cleanly. As required, it leads with the
research-use disclaimer and ends with provenance.
"""

from __future__ import annotations

import re

from alleleforge.report.builder import (
    DEFAULT_RENDER_CANDIDATES,
    NOMINATED_SITES_NOTE,
    VARIANT_POSITION_NOTE,
    WITHHELD_ALLELES_NOTE,
    WITHHELD_CANDIDATES_NOTE,
    CandidateReport,
    DesignReport,
    caveats,
    model_limitation_lines,
    provenance_lines,
    uncovered_prediction_notes,
    visible_candidates,
)
from alleleforge.report.oligos import PegRNAOligos, SgRnaOligos

#: US Letter media box (points).
_PAGE_W, _PAGE_H = 612, 792
_MARGIN = 54
_FONT_SIZE = 10
_LEADING = 14
#: Nominal characters per line, kept only for the horizontal rules that separate
#: sections. Wrapping no longer uses it: see `_wrap`.
_WRAP = 92
_TOP = _PAGE_H - _MARGIN
_LINES_PER_PAGE = int((_TOP - _MARGIN) // _LEADING)

#: Text column, in points.
_TEXT_W = _PAGE_W - 2 * _MARGIN

#: Adobe Helvetica advance widths, per 1000 em, for the glyphs these reports emit.
#: Helvetica is proportional, and wrapping at a fixed *character* count assumes it is
#: not: 92 characters is 460pt of lowercase prose and 614pt of upper-case DNA, on a
#: 504pt column. A 180-nt HDR donor — the sequence a bench scientist copies into a
#: vendor form — ran 110pt past the right margin, which on paper is off the page.
_HELVETICA_W: dict[str, int] = {
    " ": 278,
    "!": 278,
    '"': 355,
    "#": 556,
    "$": 556,
    "%": 889,
    "&": 667,
    "'": 191,
    "(": 333,
    ")": 333,
    "*": 389,
    "+": 584,
    ",": 278,
    "-": 333,
    ".": 278,
    "/": 278,
    ":": 278,
    ";": 278,
    "<": 584,
    "=": 584,
    ">": 584,
    "?": 556,
    "@": 1015,
    "[": 278,
    "\\": 278,
    "]": 278,
    "^": 469,
    "_": 556,
    "`": 333,
    "{": 334,
    "|": 260,
    "}": 334,
    "~": 584,
    **dict.fromkeys("0123456789", 556),
    **dict(
        zip(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            (
                667,
                667,
                722,
                722,
                667,
                611,
                778,
                722,
                278,
                500,
                667,
                556,
                833,
                722,
                778,
                667,
                778,
                722,
                667,
                611,
                722,
                667,
                944,
                667,
                667,
                611,
            ),
            strict=True,
        )
    ),
    **dict(
        zip(
            "abcdefghijklmnopqrstuvwxyz",
            (
                556,
                556,
                500,
                556,
                556,
                278,
                556,
                556,
                222,
                222,
                500,
                222,
                833,
                556,
                556,
                556,
                556,
                333,
                500,
                278,
                556,
                500,
                722,
                500,
                500,
                500,
            ),
            strict=True,
        )
    ),
}

#: Advance for a glyph the table does not name (an em dash, an accented letter). The
#: mid-range default keeps an unusual character from silently widening a line.
_DEFAULT_ADVANCE = 556


def _text_width(text: str) -> float:
    """Return the rendered width of ``text`` in points at :data:`_FONT_SIZE`."""
    total = sum(_HELVETICA_W.get(ch, _DEFAULT_ADVANCE) for ch in text)
    return total / 1000.0 * _FONT_SIZE


def _rule(char: str) -> str:
    """Return a horizontal rule of ``char`` that fills the column and no more."""
    per = _HELVETICA_W.get(char, _DEFAULT_ADVANCE) / 1000.0 * _FONT_SIZE
    return char * int(_TEXT_W // per)


#: A line that is nothing but nucleotides, with or without the 5'/3' markers. A long
#: sequence is wrapped across several of these, and they must not be separated.
_SEQUENCE_LINE = re.compile(r"\s*(?:5'-)?[ACGTN]{12,}(?:-3')?\s*$")


def _paginate(lines: list[str]) -> list[list[str]]:
    """Split ``lines`` into pages without breaking a wrapped sequence across two.

    Pages used to be a blind fixed-size chunk. A 180-nt HDR donor wraps to three lines,
    and with the right amount of content above it those land at 46, 47 and 48 — two at
    the foot of one page and one at the head of the next. Someone copying that donor off
    the printed sheet into a vendor form has to notice it continues overleaf, and the
    failure when they do not is a truncated reagent, which is the same consequence the
    measured line wrapping was introduced to prevent.

    A run of sequence lines that would straddle a break is moved whole to the next page.
    Nothing else is reflowed: a run longer than a page is emitted as it comes, because
    breaking it somewhere is unavoidable and pretending otherwise would loop.
    """
    pages: list[list[str]] = []
    page: list[str] = []
    index = 0
    while index < len(lines):
        run = 1
        if _SEQUENCE_LINE.match(lines[index]):
            while index + run < len(lines) and _SEQUENCE_LINE.match(lines[index + run]):
                run += 1
        room = _LINES_PER_PAGE - len(page)
        if run > room and run <= _LINES_PER_PAGE and page:
            pages.append(page)
            page = []
            room = _LINES_PER_PAGE
        take = min(run, room)
        page.extend(lines[index : index + take])
        index += take
        if len(page) >= _LINES_PER_PAGE:
            pages.append(page)
            page = []
    if page or not pages:
        pages.append(page)
    return pages


def _wrap(text: str, *, indent: str = "") -> list[str]:
    """Wrap one logical line to the page column, measured, preserving an indent.

    Measured rather than counted, because Helvetica is proportional. A single token
    wider than the column — a 180-nt donor sequence is one token — is broken at the
    last character that fits rather than allowed to run off the page: a truncated
    sequence on an order sheet is worse than a wrapped one.
    """
    limit = _TEXT_W - _text_width(indent)
    lines: list[str] = []
    current = ""
    started = False
    for token in text.split(" "):
        # Runs of spaces are preserved: `top    5'-…` and `bottom 5'-…` are aligned by
        # padding, and collapsing it puts the two sequences on different columns of the
        # sheet someone reads them off. Splitting on a single space yields empty tokens
        # for a run, and joining them back with one space is lossless.
        while _text_width(token) > limit:
            cut = len(token)
            while cut > 1 and _text_width(token[:cut]) > limit:
                cut -= 1
            if started:
                lines.append(current)
            lines.append(token[:cut])
            current, started = "", False
            token = token[cut:]
        candidate = f"{current} {token}" if started else token
        if started and _text_width(candidate) > limit:
            lines.append(current)
            current = token
        else:
            current = candidate
        started = True
    if current or not lines:
        lines.append(current)
    return [indent + line for line in lines]


def oligo_lines(oligos: SgRnaOligos | PegRNAOligos) -> list[str]:
    """Render the cloning oligos to order, with warnings and the prep note.

    The PDF is the printable leave-behind, so it must carry the exact oligos to
    order — and the phosphorylation/annealing prerequisite, without which the
    ligation cannot close — not just point at the electronic report.
    """
    scheme = oligos.scheme
    lines = _wrap(f"cloning oligos ({scheme.name}, {scheme.enzyme}):", indent="    ")
    # Hazards first, above the sequences. This is the sheet someone orders from: they
    # read the header, copy `top` and `bottom` into a vendor form, and stop. A warning
    # that the assembly enzyme cuts this very insert used to sit below what they came
    # for, between the U6 note and the ligation prep, in the same indent as both.
    for warning in oligos.warnings:
        lines += _wrap(f"WARNING: {warning}", indent="      ")
    if isinstance(oligos, SgRnaOligos):
        lines += _wrap(f"top    5'-{oligos.top}-3'", indent="      ")
        lines += _wrap(f"bottom 5'-{oligos.bottom}-3'", indent="      ")
        if oligos.g_added:
            # The ordered reagent is not the spacer that was scored. U6 needs a 5' G,
            # so the scheme prepends one — every efficiency and off-target number on
            # this page describes the 20-nt spacer, and the duplex below encodes 21 nt.
            # The HTML buries this in a JSON dump of the oligo record; the PDF is the
            # sheet someone orders from, and it said nothing.
            lines += _wrap(
                f"note: a 5' G was prepended for U6 transcription, so the cloned guide "
                f"is {len(oligos.spacer) + 1} nt; the scores above are for the "
                f"{len(oligos.spacer)}-nt spacer {oligos.spacer}",
                indent="      ",
            )
    else:
        lines += _wrap(f"spacer top    5'-{oligos.spacer_top}-3'", indent="      ")
        lines += _wrap(f"spacer bottom 5'-{oligos.spacer_bottom}-3'", indent="      ")
        lines += _wrap(f"ext top    5'-{oligos.ext_top}-3'", indent="      ")
        lines += _wrap(f"ext bottom 5'-{oligos.ext_bottom}-3'", indent="      ")
        if oligos.nicking is not None:
            lines += _wrap(f"ngRNA top    5'-{oligos.nicking.top}-3'", indent="      ")
            lines += _wrap(f"ngRNA bottom 5'-{oligos.nicking.bottom}-3'", indent="      ")
    donor = oligos.donor if isinstance(oligos, SgRnaOligos) else None
    if donor is not None:
        # Half the reagent. A precise nuclease edit is a guide *and* its repair
        # template — `oligos_for` pairs them for exactly that reason — and the printable
        # order sheet listed only the duplex, without the donor sequence or even the
        # word "donor". The candidate line above says "+ HDR donor 100 nt", so a reader
        # knew one existed and had no way to order it from this page.
        recut = "re-cut blocked" if donor.recut_blocked else "re-cut NOT blocked"
        lines += _wrap(f"HDR donor ({donor.kind}, {len(donor)} nt, {recut}):", indent="    ")
        lines += _wrap(f"5'-{donor.sequence}-3'", indent="      ")
        if donor.note:
            lines += _wrap(f"note: {donor.note}", indent="      ")
        # The donor's own hazards are not repeated here. They are promoted into
        # `oligos.warnings` (prefixed `donor:`) and printed once, at the top — this
        # loop printed them a second time as `WARNING - ...`, so every donor hazard
        # appeared twice on the sheet, differing only in punctuation, and a reader
        # counting hazards counted four where there were two.

    if scheme.phosphorylation:
        lines += _wrap(f"prep: {scheme.phosphorylation}", indent="      ")
    return lines


def _candidate_lines(c: CandidateReport) -> list[str]:
    """Render one candidate to a list of text lines."""
    lines: list[str] = []
    front = "  [Pareto-optimal]" if c.on_pareto_front else ""
    lines += _wrap(f"#{c.rank}  {c.chemistry.value}{front}")
    lines += _wrap(c.reagent, indent="    ")
    # The locus belongs on the printable sheet too: it is what a bench reader checks
    # in a browser before ordering anything.
    if c.locus is not None:
        lines += _wrap(c.locus, indent="    ")
    if c.efficiency is not None:
        e = c.efficiency
        ood = "" if e.in_distribution else "  (OUT-OF-DISTRIBUTION)"
        cal = "" if e.calibrated else "  (nominal - coverage not measured)"
        # The point estimate's own provenance, not the interval's: `calibrated=False`
        # qualifies the band, `point_from_trained_model=False` qualifies the number.
        untrained = (
            ""
            if e.point_from_trained_model
            else f"  ({e.method.value} point estimate - not from a trained model)"
        )
        lines += _wrap(
            f"efficiency {e.value:.2f} [{e.interval[0]:.2f}, {e.interval[1]:.2f}] "
            f"@ {e.interval_level:.0%}{cal}{untrained}{ood}",
            indent="    ",
        )
    if c.bystander_burden is not None:
        b = c.bystander_burden
        cal = "" if b.calibrated else "  (nominal - coverage not measured)"
        lines += _wrap(
            f"bystander burden {b.value:.2f} [{b.interval[0]:.2f}, {b.interval[1]:.2f}] "
            f"@ {b.interval_level:.0%}{cal}",
            indent="    ",
        )
    for note in uncovered_prediction_notes(c):
        lines += _wrap(f"note: {note}", indent="    ")
    if c.p_intended is not None:
        prediction = c.p_intended_prediction
        if prediction is None:
            lines += _wrap(
                f"P(intended) = {c.p_intended:.2f} (derived from the outcome "
                "distribution; no calibrated interval)",
                indent="    ",
            )
        else:
            cal = "" if prediction.calibrated else " (nominal - coverage not measured)"
            untrained = (
                ""
                if prediction.point_from_trained_model
                else f" ({prediction.method.value} point estimate - not from a trained model)"
            )
            ood = "" if prediction.in_distribution else " (out of distribution)"
            lines += _wrap(
                f"P(intended) = {prediction.value:.2f} "
                f"[{prediction.interval[0]:.2f}, {prediction.interval[1]:.2f}] "
                f"@ {prediction.interval_level:.0%}{cal}{untrained}{ood}",
                indent="    ",
            )
    for a in c.outcome_top:
        mark = " (intended)" if a.is_intended else ""
        lines += _wrap(f"outcome {a.allele}  p={a.probability:.3f}{mark}", indent="      ")
    if c.n_outcome_alleles > len(c.outcome_top):
        lines += _wrap(
            f"showing {len(c.outcome_top)} of {c.n_outcome_alleles} predicted alleles "
            f"({c.outcome_shown_mass:.2f} of the probability mass); "
            f"{WITHHELD_ALLELES_NOTE}",
            indent="      ",
        )
    burden = (
        f", expected burden {c.offtarget_expected_burden:.3f} frequency-weighted"
        if c.offtarget_expected_burden is not None
        else ""
    )
    if c.offtarget_worst_matrix is not None:
        burden += f", worst site scored by {c.offtarget_worst_matrix}"
    spec = (
        f" (specificity {c.offtarget_specificity:.3f}{burden})"
        if c.offtarget_specificity is not None
        else ""
    )
    if c.offtarget_by_ancestry:
        lines += _wrap(f"off-target sites: {c.n_offtarget_sites}{spec}", indent="    ")
        for r in c.offtarget_by_ancestry:
            lines += _wrap(
                f"{r.ancestry}: worst score {r.worst_score:.3f}, "
                f"expected burden {r.expected_burden:.4f}",
                indent="      ",
            )
    elif c.n_offtarget_sites is not None:
        lines += _wrap(f"off-target sites: {c.n_offtarget_sites}{spec}", indent="    ")
    if c.n_offtarget_sites:
        lines += _wrap(NOMINATED_SITES_NOTE, indent="      ")
    if c.n_offtarget_sites is not None and (c.offtarget_scorer or c.offtarget_matrix):
        basis = " / ".join(p for p in (c.offtarget_scorer, c.offtarget_matrix) if p)
        cite = f" — {c.offtarget_scorer_citation}" if c.offtarget_scorer_citation else ""
        lines += _wrap(f"scoring basis: {basis}{cite}", indent="      ")
    if c.offtarget_search is not None:
        lines += _wrap(f"search: {c.offtarget_search}", indent="      ")
    for flag, reason in caveats(c.flags):
        lines += _wrap(f"CAVEAT - {flag}: {reason}", indent="    ")
    if c.flags:
        lines += _wrap("flags: " + ", ".join(c.flags), indent="    ")
    if c.oligos is not None:
        lines += oligo_lines(c.oligos)
    elif c.oligos_requested:
        lines += _wrap("cloning oligos: none required (no synthesized reagent)", indent="    ")
    if c.rationale:
        # The printable leave-behind must carry the ranking rationale too — HTML and
        # JSON render it, and it explains *why* the candidate ranks where it does.
        lines += _wrap(c.rationale, indent="    ")
    lines.append("")
    return lines


def _report_lines(report: DesignReport, max_candidates: int | None) -> list[str]:
    """Flatten the whole report into the text lines to paginate."""
    lines: list[str] = []
    lines += _wrap(report.title)
    lines.append(_rule("="))
    lines += _wrap("RESEARCH USE ONLY")
    lines += _wrap(report.disclaimer)
    lines.append("")
    variant = report.variant or "(unspecified)"
    lines += _wrap(f"Variant: {variant}    Intent: {report.intent or '(default)'}")
    if report.variant:
        lines += _wrap(f"({VARIANT_POSITION_NOTE})")
    if report.weights:
        weights = ", ".join(f"{k} {v:.2f}" for k, v in report.weights.items())
        lines += _wrap(f"Ranking weights: {weights}")
    lines.append("")
    if report.unavailable:
        # Before the rationale, for the same reason the HTML puts it above: this is why
        # part of the menu is missing, not one of the routing verdicts a reader skims.
        lines += _wrap("PART OF THIS MENU IS MISSING")
        for note in report.unavailable:
            lines += _wrap(f"- {note}")
        lines.append("")
    if report.rationale:
        lines += _wrap("HOW THIS MENU WAS ASSEMBLED")
        for para in report.rationale.split("\n"):
            lines += _wrap(para)
        lines.append("")
    lines += _wrap(f"Candidates ({len(report.candidates)})")
    lines.append(_rule("-"))
    shown, withheld = visible_candidates(report, max_candidates)
    if withheld:
        lines += _wrap(
            f"Showing {len(shown)} of {len(report.candidates)}: the top {max_candidates} by "
            f"rank plus every Pareto-front candidate. The remaining {withheld} are not "
            f"lost: {WITHHELD_CANDIDATES_NOTE}."
        )
        lines.append("")
    if shown:
        for c in shown:
            lines += _candidate_lines(c)
    else:
        lines += _wrap("No candidates were produced for this variant.")
    lines.append(_rule("-"))
    provenance = provenance_lines(report.provenance)
    if provenance:
        lines += _wrap("PROVENANCE")
        lines += _wrap("; ".join(provenance))
    limits = model_limitation_lines(report.provenance)
    if limits:
        lines += _wrap("MODEL LIMITATIONS")
        for line in limits:
            lines += _wrap(line, indent="  ")
    return lines


def _escape(text: str) -> str:
    """Escape a string for a PDF literal, dropping only truly unrenderable chars.

    The font is declared ``/WinAnsiEncoding`` (CP1252), so encode to CP1252, not
    Latin-1: CP1252 is a superset in ``0x80-0x9F`` that carries the ordinary
    punctuation Latin-1 would silently turn into ``?`` — a curly apostrophe
    (``'``), en/em dashes (``-``/``--``), and the euro sign (``EUR``) — which the PDF's
    own font renders. Genuinely unrepresentable characters (e.g. non-Latin scripts)
    still become ``?``, unavoidable in a Helvetica/WinAnsi core font.
    """
    safe = text.encode("cp1252", "replace").decode("cp1252")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(page_lines: list[str]) -> bytes:
    """Build a page's content stream from its text lines."""
    parts = [f"BT /F1 {_FONT_SIZE} Tf {_MARGIN} {_TOP} Td {_LEADING} TL"]
    for line in page_lines:
        parts.append(f"({_escape(line)}) Tj T*")
    parts.append("ET")
    return "\n".join(parts).encode("cp1252")  # matches the declared WinAnsiEncoding font


def _pdf_text_string(text: str) -> bytes:
    """Return ``text`` as a PDF *text string*, ASCII literal or UTF-16BE hex.

    Not the encoding the page content uses. `WinAnsiEncoding` is a property of the font
    the body is drawn with; a string in the document information dictionary is a PDF
    text string, read as PDFDocEncoding unless it opens with a UTF-16 byte-order mark.
    Writing the title in the body's encoding put a `Š` in the middle of the document's
    own name — visible only by opening the file with a real reader, which is how it was
    found.

    ASCII stays a plain literal so the common case reads as text in the file itself.
    """
    if text.isascii():
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return b"(" + escaped.encode("ascii") + b")"
    return b"<" + (b"\xfe\xff" + text.encode("utf-16-be")).hex().upper().encode("ascii") + b">"


def _info_object(report: DesignReport) -> bytes:
    """Return the document information dictionary.

    A PDF's `/Title` is what a viewer puts in the window bar and what a reference
    manager files the document under. This writer emitted no `/Info` at all, so a
    forty-five-page report handed to a colleague opened untitled and was filed as one —
    while the HTML rendering of the same report has carried a `<title>` all along.

    No `/CreationDate`: the same report must render to the same bytes, and a clock in
    the metadata would make every run differ from the golden by exactly the field
    nobody reads.
    """
    # `report.title` rather than a string spelled again here: it is the name the
    # document already gives itself on its own first page and in the HTML `<title>`,
    # so the three cannot drift apart.
    title = f"{report.title} — {report.variant}"
    version = report.provenance.alleleforge_version if report.provenance else None
    producer = f"AlleleForge {version}" if version else "AlleleForge"
    return (
        b"<< /Title "
        + _pdf_text_string(title)
        + b" /Producer "
        + _pdf_text_string(producer)
        + b" /Creator "
        + _pdf_text_string(producer)
        + b" >>"
    )


def render_pdf(
    report: DesignReport, *, max_candidates: int | None = DEFAULT_RENDER_CANDIDATES
) -> bytes:
    """Render a :class:`DesignReport` to a valid, print-ready PDF document.

    Args:
        report: The report to render.
        max_candidates: How many ranked candidates to draw, or ``None`` for all.
            Every Pareto-front candidate is drawn whatever the cap, and any
            withheld count is stated in the document — the same contract the HTML
            render honors, through the same shared helper.

    Returns:
        The PDF file contents as bytes (begins ``%PDF-1.4``, ends ``%%EOF``).
    """
    lines = _report_lines(report, max_candidates)
    pages = _paginate(lines)

    # Object numbering: 1 catalog, 2 pages, 3 font, 4 info, then page/content objects.
    n_pages = len(pages)
    page_obj_nums = [5 + i for i in range(n_pages)]
    content_obj_nums = [5 + n_pages + i for i in range(n_pages)]
    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("latin-1"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: _info_object(report),
    }
    for i, page in enumerate(pages):
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_W} {_PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_obj_nums[i]} 0 R >>"
        ).encode("latin-1")
        objects[page_obj_nums[i]] = page_obj
        stream = _content_stream(page)
        objects[content_obj_nums[i]] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        )

    # Serialize with a byte-accurate cross-reference table.
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode("latin-1") + objects[num] + b"\nendobj\n"

    xref_pos = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for num in range(1, count):
        out += f"{offsets[num]:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {count} /Root 1 0 R /Info 4 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode("latin-1")
    return bytes(out)
