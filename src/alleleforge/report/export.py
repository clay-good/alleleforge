"""Machine-readable export of a design report: JSON, TSV, and Parquet.

JSON is the lossless form (the full :class:`~alleleforge.report.builder.DesignReport`,
or the underlying :class:`~alleleforge.types.candidate.RankedMenu` validated
against the Phase 1 schemas). TSV is the flat, one-row-per-candidate form for
spreadsheets and pipelines. Parquet is the columnar form for batch runs and is
the only export with an optional dependency (``polars``), imported lazily so the
core install never pulls it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alleleforge.errors import MissingDependencyError
from alleleforge.report.builder import DesignReport, caveats, provenance_lines
from alleleforge.types.candidate import RankedMenu

#: Schema version for the flat TSV/Parquet candidate export. Bump when a column is
#: added, removed, or reinterpreted so a downstream consumer can detect the drift —
#: and for v6, when the TSV grew its leading `#` note block, which a reader that skips
#: no comments does see.
EXPORT_SCHEMA_VERSION = 8

#: The flat TSV column order (one row per candidate). ``schema_version`` leads so a
#: reader can branch on the format before touching any other column.
TSV_COLUMNS = (
    "schema_version",
    "rank",
    "chemistry",
    # Where the edit lands. A pipeline cannot join a candidate row to anything genomic
    # without it, and no column carried a contig.
    "locus",
    "on_pareto_front",
    "efficiency",
    "efficiency_low",
    "efficiency_high",
    "in_distribution",
    "calibrated",
    "bystander_burden",
    "p_intended",
    # The same three qualifiers `efficiency` carries. `p_intended` alone is the
    # number a pipeline filters on, and without these a derived sum over an indel
    # spectrum and a calibrated prediction are the same column.
    "p_intended_low",
    "p_intended_high",
    "p_intended_in_distribution",
    "p_intended_calibrated",
    "n_offtarget_sites",
    # `n_offtarget_sites` alone is not a safety number. It is conditional on the
    # cut-offs that produced it and it says nothing about the aggregate, both of which
    # the HTML and PDF renders have carried since they were added — while this export,
    # the one a pipeline actually filters on, carried neither. A row that reads
    # `n_offtarget_sites = 0` is uninterpretable and comparable to nothing.
    "offtarget_specificity",
    # Empty unless some site's presence is probabilistic — with reference sites alone
    # the burden is the unweighted score sum and says nothing the specificity does not.
    # When it is populated it is the only column separating a rare-variant off-target
    # from a universal one, which is the whole point of a population-aware search.
    "offtarget_expected_burden",
    "offtarget_scorer",
    "offtarget_matrix",
    "offtarget_scorer_citation",
    "offtarget_search",
    "worst_ancestry",
    "worst_ancestry_score",
    "flags",
    # The hazard subset of `flags`, so a pipeline can filter on "needs attention"
    # without hard-coding which flag names are hazards — a list that grows.
    "caveats",
    "rationale",
    "reagent",
)


def report_to_json(report: DesignReport, *, indent: int | None = 2) -> str:
    """Serialize the full report to JSON (lossless)."""
    return report.model_dump_json(indent=indent)


def menu_to_json(menu: RankedMenu, *, indent: int | None = 2) -> str:
    """Serialize the underlying ranked menu to schema-valid Phase 1 JSON."""
    return menu.model_dump_json(indent=indent)


def _row(candidate: Any) -> dict[str, Any]:
    """Flatten one :class:`CandidateReport` into a TSV/Parquet row dict."""
    eff = candidate.efficiency
    # `None` for a chemistry whose outcome predictor makes no such prediction; the
    # four columns are then blank, which is the difference between "no interval was
    # computed" and "the interval is zero-width".
    pi = candidate.p_intended_prediction
    burden = candidate.bystander_burden
    worst = candidate.offtarget_by_ancestry[0] if candidate.offtarget_by_ancestry else None
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "rank": candidate.rank,
        "chemistry": candidate.chemistry.value,
        "locus": candidate.locus,
        "on_pareto_front": candidate.on_pareto_front,
        "efficiency": None if eff is None else round(eff.value, 4),
        "efficiency_low": None if eff is None else round(eff.interval[0], 4),
        "efficiency_high": None if eff is None else round(eff.interval[1], 4),
        "in_distribution": None if eff is None else eff.in_distribution,
        "calibrated": None if eff is None else eff.calibrated,
        "bystander_burden": None if burden is None else round(burden.value, 4),
        "p_intended": None if candidate.p_intended is None else round(candidate.p_intended, 4),
        "p_intended_low": None if pi is None else round(pi.interval[0], 4),
        "p_intended_high": None if pi is None else round(pi.interval[1], 4),
        "p_intended_in_distribution": None if pi is None else pi.in_distribution,
        "p_intended_calibrated": None if pi is None else pi.calibrated,
        "n_offtarget_sites": candidate.n_offtarget_sites,
        "offtarget_expected_burden": (
            ""
            if candidate.offtarget_expected_burden is None
            else round(candidate.offtarget_expected_burden, 4)
        ),
        "offtarget_specificity": (
            None
            if candidate.offtarget_specificity is None
            else round(candidate.offtarget_specificity, 4)
        ),
        "offtarget_scorer": candidate.offtarget_scorer,
        "offtarget_matrix": candidate.offtarget_matrix,
        "offtarget_scorer_citation": candidate.offtarget_scorer_citation,
        "offtarget_search": candidate.offtarget_search,
        "worst_ancestry": None if worst is None else worst.ancestry,
        "worst_ancestry_score": None if worst is None else round(worst.worst_score, 4),
        "flags": ";".join(candidate.flags),
        "caveats": ";".join(flag for flag, _ in caveats(candidate.flags)),
        "rationale": candidate.rationale,
        "reagent": candidate.reagent,
    }


def _cell(value: Any) -> str:
    """Render one cell for TSV (empty for ``None``, no embedded tabs/newlines)."""
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _tsv_notes(report: DesignReport) -> list[str]:
    """Return the `#`-prefixed lines that must precede the table.

    The HTML, the PDF and the JSON all carry the research-use disclaimer, the
    coordinate convention and the provenance footer. The TSV carried none of them,
    which left the one format a reader opens in a spreadsheet showing efficiencies,
    specificities and genomic loci with nothing saying they are uncertain
    computational predictions, against which genome, in which coordinate convention.

    `#` is what VCF, GTF and bedGraph use, so the column header stays the first
    non-comment line and a comment-skipping reader gets an identical table.

    Args:
        report: The report being serialized.

    Returns:
        Comment lines, each already `#`-prefixed and free of tabs and newlines.
    """
    notes = [report.disclaimer, *provenance_lines(report.provenance)]
    return [f"# {_cell(note)}" for note in notes if note]


def report_to_tsv(report: DesignReport) -> str:
    """Serialize the report to TSV: `#` notes, a header, one row per candidate."""
    lines = [*_tsv_notes(report), "\t".join(TSV_COLUMNS)]
    for candidate in report.candidates:
        row = _row(candidate)
        lines.append("\t".join(_cell(row[col]) for col in TSV_COLUMNS))
    return "\n".join(lines) + "\n"


def report_to_parquet(report: DesignReport, path: str | Path) -> Path:
    """Write the flat per-candidate table to a Parquet file.

    Args:
        report: The report to export.
        path: Destination ``.parquet`` path.

    Returns:
        The written path.

    Raises:
        RuntimeError: If the optional ``polars`` dependency is not installed.
    """
    try:
        import polars as pl
    except ImportError as exc:  # pragma: no cover - exercised only without polars
        raise MissingDependencyError(
            "Parquet export requires the optional 'polars' dependency (install alleleforge[core])"
        ) from exc
    rows = [_row(c) for c in report.candidates]
    frame = pl.DataFrame(rows) if rows else pl.DataFrame({col: [] for col in TSV_COLUMNS})
    out = Path(path)
    frame.write_parquet(out)
    return out
