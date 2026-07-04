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

from alleleforge.report.builder import DesignReport
from alleleforge.types.candidate import RankedMenu

#: Schema version for the flat TSV/Parquet candidate export. Bump when a column is
#: added, removed, or reinterpreted so a downstream consumer can detect the drift.
EXPORT_SCHEMA_VERSION = 1

#: The flat TSV column order (one row per candidate). ``schema_version`` leads so a
#: reader can branch on the format before touching any other column.
TSV_COLUMNS = (
    "schema_version",
    "rank",
    "chemistry",
    "on_pareto_front",
    "efficiency",
    "efficiency_low",
    "efficiency_high",
    "in_distribution",
    "bystander_burden",
    "p_intended",
    "n_offtarget_sites",
    "worst_ancestry",
    "worst_ancestry_score",
    "flags",
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
    burden = candidate.bystander_burden
    worst = candidate.offtarget_by_ancestry[0] if candidate.offtarget_by_ancestry else None
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "rank": candidate.rank,
        "chemistry": candidate.chemistry.value,
        "on_pareto_front": candidate.on_pareto_front,
        "efficiency": None if eff is None else round(eff.value, 4),
        "efficiency_low": None if eff is None else round(eff.interval[0], 4),
        "efficiency_high": None if eff is None else round(eff.interval[1], 4),
        "in_distribution": None if eff is None else eff.in_distribution,
        "bystander_burden": None if burden is None else round(burden.value, 4),
        "p_intended": None if candidate.p_intended is None else round(candidate.p_intended, 4),
        "n_offtarget_sites": candidate.n_offtarget_sites,
        "worst_ancestry": None if worst is None else worst.ancestry,
        "worst_ancestry_score": None if worst is None else round(worst.worst_score, 4),
        "flags": ";".join(candidate.flags),
        "reagent": candidate.reagent,
    }


def _cell(value: Any) -> str:
    """Render one cell for TSV (empty for ``None``, no embedded tabs/newlines)."""
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")


def report_to_tsv(report: DesignReport) -> str:
    """Serialize the report to TSV: a header plus one row per candidate."""
    lines = ["\t".join(TSV_COLUMNS)]
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
        raise RuntimeError(
            "Parquet export requires the optional 'polars' dependency (install alleleforge[core])"
        ) from exc
    rows = [_row(c) for c in report.candidates]
    frame = pl.DataFrame(rows) if rows else pl.DataFrame({col: [] for col in TSV_COLUMNS})
    out = Path(path)
    frame.write_parquet(out)
    return out
