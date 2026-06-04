"""Reporting & oligo output (Phase 11).

Turns a ranked design menu into the artifacts users actually consume: cloning-
ready oligos (:mod:`.oligos`), a structured serializable report model
(:mod:`.builder`), machine-readable JSON / TSV / Parquet (:mod:`.export`), an
interactive self-contained HTML page (:mod:`.html`), and a static print-ready
PDF (:mod:`.pdf`). Every render leads with the research-use disclaimer and ends
with full provenance.
"""

from __future__ import annotations

from alleleforge.report.builder import (
    RESEARCH_USE_DISCLAIMER,
    AncestryOffTarget,
    CandidateReport,
    DesignReport,
    build_report,
)
from alleleforge.report.export import (
    menu_to_json,
    report_to_json,
    report_to_parquet,
    report_to_tsv,
)
from alleleforge.report.html import render_html
from alleleforge.report.oligos import (
    LENTIGUIDE_BSMBI,
    PEGRNA_GG_BSAI,
    PX330_BBSI,
    PegRNAOligos,
    SgRnaOligos,
    VectorScheme,
    oligos_for,
    pegrna_oligos,
    sgrna_oligos,
)
from alleleforge.report.pdf import render_pdf

__all__ = [
    "LENTIGUIDE_BSMBI",
    "PEGRNA_GG_BSAI",
    "PX330_BBSI",
    "RESEARCH_USE_DISCLAIMER",
    "AncestryOffTarget",
    "CandidateReport",
    "DesignReport",
    "PegRNAOligos",
    "SgRnaOligos",
    "VectorScheme",
    "build_report",
    "menu_to_json",
    "oligos_for",
    "pegrna_oligos",
    "render_html",
    "render_pdf",
    "report_to_json",
    "report_to_parquet",
    "report_to_tsv",
    "sgrna_oligos",
]
