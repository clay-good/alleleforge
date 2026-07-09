"""Render a design report as a static, print-ready PDF — no dependencies.

A full PDF toolchain (weasyprint, reportlab) is heavy and platform-fragile, so
this module ships a small, self-contained writer that emits a valid multi-page
PDF 1.4 with Helvetica text. It is deliberately text-and-table oriented: the
interactive charts live in the HTML render ([`render_html`][alleleforge.report.html.render_html]);
the PDF is the leave-behind that prints cleanly. As required, it leads with the
research-use disclaimer and ends with provenance.
"""

from __future__ import annotations

import textwrap

from alleleforge.report.builder import CandidateReport, DesignReport
from alleleforge.report.oligos import PegRNAOligos, SgRnaOligos

#: US Letter media box (points).
_PAGE_W, _PAGE_H = 612, 792
_MARGIN = 54
_FONT_SIZE = 10
_LEADING = 14
_WRAP = 92  # characters per line at 10pt Helvetica within the margins
_TOP = _PAGE_H - _MARGIN
_LINES_PER_PAGE = int((_TOP - _MARGIN) // _LEADING)


def _wrap(text: str, *, indent: str = "") -> list[str]:
    """Wrap one logical line to the page width (preserving an indent)."""
    wrapped = textwrap.wrap(text, width=_WRAP - len(indent)) or [""]
    return [indent + line for line in wrapped]


def _oligo_lines(oligos: SgRnaOligos | PegRNAOligos) -> list[str]:
    """Render the cloning oligos to order, with warnings and the prep note.

    The PDF is the printable leave-behind, so it must carry the exact oligos to
    order — and the phosphorylation/annealing prerequisite, without which the
    ligation cannot close — not just point at the electronic report.
    """
    scheme = oligos.scheme
    lines = _wrap(f"cloning oligos ({scheme.name}, {scheme.enzyme}):", indent="    ")
    if isinstance(oligos, SgRnaOligos):
        lines += _wrap(f"top    5'-{oligos.top}-3'", indent="      ")
        lines += _wrap(f"bottom 5'-{oligos.bottom}-3'", indent="      ")
    else:
        lines += _wrap(f"spacer top    5'-{oligos.spacer_top}-3'", indent="      ")
        lines += _wrap(f"spacer bottom 5'-{oligos.spacer_bottom}-3'", indent="      ")
        lines += _wrap(f"ext top    5'-{oligos.ext_top}-3'", indent="      ")
        lines += _wrap(f"ext bottom 5'-{oligos.ext_bottom}-3'", indent="      ")
        if oligos.nicking is not None:
            lines += _wrap(f"ngRNA top    5'-{oligos.nicking.top}-3'", indent="      ")
            lines += _wrap(f"ngRNA bottom 5'-{oligos.nicking.bottom}-3'", indent="      ")
    for warning in oligos.warnings:
        lines += _wrap(f"WARNING: {warning}", indent="      ")
    if scheme.phosphorylation:
        lines += _wrap(f"prep: {scheme.phosphorylation}", indent="      ")
    return lines


def _candidate_lines(c: CandidateReport) -> list[str]:
    """Render one candidate to a list of text lines."""
    lines: list[str] = []
    front = "  [Pareto-optimal]" if c.on_pareto_front else ""
    lines += _wrap(f"#{c.rank}  {c.chemistry.value}{front}")
    lines += _wrap(c.reagent, indent="    ")
    if c.efficiency is not None:
        e = c.efficiency
        ood = "" if e.in_distribution else "  (OUT-OF-DISTRIBUTION)"
        lines += _wrap(
            f"efficiency {e.value:.2f} [{e.interval[0]:.2f}, {e.interval[1]:.2f}] "
            f"@ {e.interval_level:.0%}{ood}",
            indent="    ",
        )
    if c.bystander_burden is not None:
        b = c.bystander_burden
        lines += _wrap(
            f"bystander burden {b.value:.2f} [{b.interval[0]:.2f}, {b.interval[1]:.2f}] "
            f"@ {b.interval_level:.0%}",
            indent="    ",
        )
    if c.p_intended is not None:
        lines += _wrap(f"P(intended) = {c.p_intended:.2f}", indent="    ")
    for a in c.outcome_top:
        mark = " (intended)" if a.is_intended else ""
        lines += _wrap(f"outcome {a.allele}  p={a.probability:.3f}{mark}", indent="      ")
    spec = (
        f" (specificity {c.offtarget_specificity:.3f})"
        if c.offtarget_specificity is not None
        else ""
    )
    if c.offtarget_by_ancestry:
        lines += _wrap(f"off-target sites: {c.n_offtarget_sites}{spec}", indent="    ")
        for r in c.offtarget_by_ancestry:
            lines += _wrap(f"{r.ancestry}: worst score {r.worst_score:.3f}", indent="      ")
    elif c.n_offtarget_sites is not None:
        lines += _wrap(f"off-target sites: {c.n_offtarget_sites}{spec}", indent="    ")
    if c.n_offtarget_sites is not None and (c.offtarget_scorer or c.offtarget_matrix):
        basis = " / ".join(p for p in (c.offtarget_scorer, c.offtarget_matrix) if p)
        lines += _wrap(f"scoring basis: {basis}", indent="      ")
    if c.flags:
        lines += _wrap("flags: " + ", ".join(c.flags), indent="    ")
    if c.oligos is not None:
        lines += _oligo_lines(c.oligos)
    elif c.oligos_requested:
        lines += _wrap("cloning oligos: none required (no synthesized reagent)", indent="    ")
    lines.append("")
    return lines


def _report_lines(report: DesignReport) -> list[str]:
    """Flatten the whole report into the text lines to paginate."""
    lines: list[str] = []
    lines += _wrap(report.title)
    lines.append("=" * _WRAP)
    lines += _wrap("RESEARCH USE ONLY")
    lines += _wrap(report.disclaimer)
    lines.append("")
    variant = report.variant or "(unspecified)"
    lines += _wrap(f"Variant: {variant}    Intent: {report.intent or '(default)'}")
    if report.weights:
        weights = ", ".join(f"{k} {v:.2f}" for k, v in report.weights.items())
        lines += _wrap(f"Ranking weights: {weights}")
    lines.append("")
    lines += _wrap(f"Candidates ({len(report.candidates)})")
    lines.append("-" * _WRAP)
    if report.candidates:
        for c in report.candidates:
            lines += _candidate_lines(c)
    else:
        lines += _wrap("No candidates were produced for this variant.")
    lines.append("-" * _WRAP)
    p = report.provenance
    if p is not None:
        lines += _wrap("PROVENANCE")
        lines += _wrap(
            f"AlleleForge {p.alleleforge_version}; reference {p.reference_build}; "
            f"seed {p.seed}; generated {p.timestamp.isoformat()}"
        )
        if p.models:
            models = ", ".join(f"{m.name} {m.version}" for m in p.models)
            lines += _wrap(f"Models: {models}")
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


def render_pdf(report: DesignReport) -> bytes:
    """Render a :class:`DesignReport` to a valid, print-ready PDF document.

    Args:
        report: The report to render.

    Returns:
        The PDF file contents as bytes (begins ``%PDF-1.4``, ends ``%%EOF``).
    """
    lines = _report_lines(report)
    pages = [lines[i : i + _LINES_PER_PAGE] for i in range(0, len(lines), _LINES_PER_PAGE)] or [[]]

    # Object numbering: 1 catalog, 2 pages, 3 font, then page/content objects.
    n_pages = len(pages)
    page_obj_nums = [4 + i for i in range(n_pages)]
    content_obj_nums = [4 + n_pages + i for i in range(n_pages)]
    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("latin-1"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
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
    out += (f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n").encode(
        "latin-1"
    )
    return bytes(out)
