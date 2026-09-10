"""The cohort summary: one flat row per item, and the TSV a whole run is read through.

This lived in `cli/main.py`, which made it the one part of the pipeline a Python caller
could not reach and the web API could not serve — while the README says of both shells
that they carry "no business logic of its own". A cohort summary is a *product*: it is
the file a run over a patient VCF gets forwarded in, one row per person, and flattening a
`CohortRunReport` plus reproducing the `#` note block is exactly the work a caller should
not have to redo to get it.

The single-design flat table went through the same correction: it is what a pipeline
reads, so every shell must be able to produce it. This table is more pipeline-shaped than
that one.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from alleleforge._version import __version__

__all__ = [
    "COHORT_COLUMNS",
    "COHORT_COLUMN_TYPES",
    "cohort_reference_shape_suffix",
    "cohort_rows",
    "cohort_to_parquet",
    "cohort_to_tsv",
]

#: The flat cohort table's columns, in order. Declared once because the TSV and the
#: Parquet are one table in two encodings, and the pair of tables this project already
#: had drifted by one adjacent swap while both were "obviously" the same — two numbers
#: on unrelated scales under one column index.
COHORT_COLUMNS: tuple[str, ...] = (
    "item_id",
    "variant",
    "clinical_significance",
    "status",
    "best_chemistry",
    # Every chemistry that produced a candidate, not only the recommended one. A
    # cohort is scanned to decide which variants need a closer look, and "prime
    # only" and "prime, base_abe and cas9_nuclease" send a reader to very different
    # next steps. It was on the row, so a Python caller had it and the file did not.
    "chemistries",
    "best_efficiency",
    "best_efficiency_low",
    "best_efficiency_high",
    "best_efficiency_in_distribution",
    "best_caveats",
    "offtarget_sources",
    "best_bystander_burden",
    "best_bystander_burden_low",
    "best_bystander_burden_high",
    "worst_offtarget",
    "best_specificity",
    "n_candidates",
    "no_candidate_reason",
    "error",
)

#: The type each cohort column holds, for the encodings that have types.
#:
#: Declared rather than inferred, for the reason the per-candidate table records: on a
#: real cohort the first rows are not representative — `best_bystander_burden` is null
#: for every prime item and a float on the one base editor far down the run — so an
#: inferred schema either fails or gives two runs of the same tool files a pipeline
#: cannot union. The three structured columns (`chemistries`, `best_caveats`,
#: `offtarget_sources`) are `str` here because they are rendered for a flat table
#: exactly as the TSV renders them; `cohort_rows` is where a caller gets them
#: structured.
COHORT_COLUMN_TYPES: dict[str, type] = {
    "item_id": str,
    "variant": str,
    "clinical_significance": str,
    "status": str,
    "best_chemistry": str,
    "chemistries": str,
    "best_efficiency": float,
    "best_efficiency_low": float,
    "best_efficiency_high": float,
    "best_efficiency_in_distribution": bool,
    "best_caveats": str,
    "offtarget_sources": str,
    "best_bystander_burden": float,
    "best_bystander_burden_low": float,
    "best_bystander_burden_high": float,
    "worst_offtarget": float,
    "best_specificity": float,
    "n_candidates": int,
    "no_candidate_reason": str,
    "error": str,
}


def cohort_rows(report: Any) -> list[dict[str, Any]]:
    """Flatten a :class:`CohortRunReport` into one summary row per item.

    One dict per cohort item, in the run's order, with the keys
    :func:`cohort_to_tsv` writes as columns. Every value comes from the item's own
    summary; nothing is derived here, so a row for a failed item carries its
    ``error`` and ``None`` for the design fields rather than a substituted zero — the
    distinction between "not measured" and "measured as clean" that the rest of this
    project spends its effort on.

    ``best_caveats`` is a list, ``offtarget_sources`` a mapping, and both are rendered
    for a flat table by :func:`cohort_to_tsv`; a caller building their own table gets
    them structured.

    Args:
        report: The run to flatten.

    Returns:
        One summary dict per item, in run order.
    """
    rows: list[dict[str, Any]] = []
    for it in report.items:
        summary = it.summary or {}
        rows.append(
            {
                "item_id": it.item_id,
                "status": it.status,
                # Second column, beside the id it disambiguates: a reader scanning the
                # table left to right needs "what the row is about" before any number.
                "variant": summary.get("variant"),
                "clinical_significance": summary.get("clinical_significance"),
                "best_chemistry": summary.get("best_chemistry"),
                "chemistries": summary.get("chemistries") or [],
                "best_efficiency": summary.get("best_efficiency"),
                "best_efficiency_low": summary.get("best_efficiency_low"),
                "best_efficiency_high": summary.get("best_efficiency_high"),
                "best_efficiency_in_distribution": summary.get("best_efficiency_in_distribution"),
                "best_caveats": summary.get("best_caveats") or [],
                "best_bystander_burden": summary.get("best_bystander_burden"),
                "best_bystander_burden_low": summary.get("best_bystander_burden_low"),
                "best_bystander_burden_high": summary.get("best_bystander_burden_high"),
                "offtarget_sources": summary.get("offtarget_sources"),
                "worst_offtarget": summary.get("worst_offtarget"),
                "best_specificity": summary.get("best_specificity"),
                "n_candidates": summary.get("n_candidates"),
                "no_candidate_reason": summary.get("no_candidate_reason"),
                "error": it.error,
            }
        )
    return rows


def _reference_note(build: str | None, shape: Any) -> str:
    """Return the cohort summary's reference line.

    Under `--max-workers` the reference is opened per worker, so the run has no
    single genome to name and `reference_build` is `None`. Printing "reference build
    None" reads as a missing value; what is true is that each item's own menu records
    the genome it was designed against, and saying that is the difference between
    "not recorded" and "recorded elsewhere".
    """
    if build is None:
        return (
            "reference build: not recorded run-wide — the parallel path opens a "
            "reference per worker; each item's own result records the genome it used"
        )
    return f"reference build {build}{cohort_reference_shape_suffix(shape)}"


def cohort_reference_shape_suffix(shape: Any) -> str:
    """Return the parenthesized reference shape for a cohort note line.

    Mirrors the report footer's phrasing, including the statement of what the digest
    covers. Empty when the run had no single reference to describe — the parallel
    path opens one per worker, and inventing a run-wide identity there would be a
    claim nothing checked.
    """
    if not isinstance(shape, dict):
        return ""
    plural = "" if shape.get("contigs") == 1 else "s"
    digest = str(shape.get("sha256", ""))[:8]
    return (
        f" ({shape.get('contigs')} contig{plural}, {shape.get('bases'):,} bases, "
        f"shape {digest} — pins {shape.get('pins', 'an unstated extent')})"
    )


def _cell(value: Any) -> str:
    """Render one cohort cell for TSV, matching `report/export.py`'s conventions.

    This writer passed every value through `str()`, so a TSV — the format a pipeline
    reads — carried Python reprs and raw float noise::

        best_caveats            ['pol3-terminator', 'gc-out-of-band:0.20']
        offtarget_sources       {}
        best_efficiency_low     0.44999999999999996

    The report exporter formats its values before they reach the cell: floats
    rounded to four places, flags joined with `;`. A consumer should not need a
    Python parser for one of this project's two TSVs and not the other.
    """
    # Neutralize the delimiters so a tab/newline in a field (item_id is a raw
    # input line; error is an exception message) cannot misalign the TSV.
    if value is None:
        return ""
    if isinstance(value, bool):
        rendered: Any = value  # before the float branch: a bool is an int
    elif isinstance(value, float):
        rendered = round(value, 4)
    elif isinstance(value, Mapping):
        rendered = ";".join(f"{k}={v}" for k, v in sorted(value.items()))
    elif isinstance(value, (list, tuple)):
        rendered = ";".join(str(item) for item in value)
    else:
        rendered = value
    return str(rendered).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _sources(value: Any) -> Any:
    """Keep "searched, reference-only" distinct from "not searched".

    `sources_considered` names the *optional* safety sources — gnomAD, a haplotype
    panel, a patient VCF. `None` means no off-target report exists at all; `{}` means
    one does and no optional source was supplied. Rendering an empty mapping as an
    empty cell collapsed those into one string, on the axis where "we did not look"
    must never look like "we looked and found nothing".
    """
    if isinstance(value, Mapping) and not value:
        return "reference-only"
    return value


def _cohort_notes(
    rows: list[dict[str, Any]],
    provenance: Any | None,
    counts: Mapping[str, int] | None,
) -> list[str]:
    """Return the note block both cohort encodings carry, in document order.

    The TSV writes these as leading `#` lines and the Parquet as file-level key/value
    metadata. Building them once is what makes "the same table in two encodings" true
    of the notes as well as the columns — and the notes are the half that says which
    genome was searched and under which seed, without which a row per patient is not
    interpretable.
    """
    from alleleforge.design.ranking import CROSS_CHEMISTRY_NOTE
    from alleleforge.report.builder import COORDINATE_NOTE, RESEARCH_USE_DISCLAIMER

    # `CohortRunReport.provenance` is a plain dict assembled by the cohort runner,
    # not the `Provenance` model a menu carries, so the notes are built from it
    # directly rather than through `provenance_lines`.
    run = provenance or {}
    shape = run.get("reference")
    notes = [
        RESEARCH_USE_DISCLAIMER,
        f"AlleleForge {run.get('alleleforge_version', __version__)}",
        _reference_note(run.get("reference_build"), shape),
        COORDINATE_NOTE,
        f"seed {run.get('seed')}",
        f"intent {run.get('intent')}",
        f"started {run.get('started_at')}",
    ]
    # The datasets the run actually read, pinned by content hash — the same block every
    # per-item menu carries. Without it this file named the genome and nothing else, so a
    # cohort resolved through a ClinVar release could not say which release chose its
    # loci, and one made population-aware by a gnomAD file could not say which file.
    # Reported as "none recorded" rather than omitted: an absent line is indistinguishable
    # from a run that consumed no pinned dataset, and those are different runs.
    datasets = run.get("datasets")
    if datasets is not None:
        named = ", ".join(f"{d.get('name')} {d.get('version')}" for d in datasets)
        notes.append(f"datasets: {named or 'none recorded'}")
    if counts is not None:
        requested = counts.get("total", 0) + counts.get("skipped", 0)
        note = (
            f"{requested} requested, {counts.get('total', 0)} designed "
            f"({counts.get('succeeded', 0)} ok, {counts.get('failed', 0)} failed), "
            f"{counts.get('skipped', 0)} already done (resume)"
        )
        if not rows and counts.get("skipped"):
            # The case this exists for: every row is below, and there are none.
            note += " — this table is empty because the run had nothing left to design"
        notes.append(note)
    # Whether the safety columns are empty because nothing was found or because nothing
    # was looked for. Every off-target cell of an unsearched item is blank, which reads
    # from the outside like a clean result — the distinction this project spends its
    # effort on, missing from the file a cohort is forwarded in. The rows already carry
    # it: `offtarget_sources` is `None` when no report exists and `"reference-only"` when
    # one does with no optional source.
    designed = [r for r in rows if r.get("status") == "ok"]
    unsearched = [r for r in designed if r.get("offtarget_sources") is None]
    if designed and len(unsearched) == len(designed):
        notes.append(
            "no off-target search was run for any item: every off-target column below is "
            "empty because nothing was looked for, not because nothing was found"
        )
    elif unsearched:
        notes.append(
            f"{len(unsearched)} of {len(designed)} designed item(s) had no off-target "
            "search, so their off-target columns are empty for want of a search rather "
            "than of a finding"
        )
    # A source that disagrees with the reference. Said once for the whole run rather
    # than left in five hundred rows: a file built against another assembly produces the
    # same qualified cell on every one of them, and nobody reads five hundred cells to
    # notice a constant. The per-row key stays, for whatever reads the table.
    mismatched: dict[str, int] = {}
    for row in designed:
        sources = row.get("offtarget_sources")
        if isinstance(sources, Mapping):
            for key, count in sources.items():
                if key.endswith(":build-mismatch") and isinstance(count, int):
                    mismatched[key.removesuffix(":build-mismatch")] = max(
                        mismatched.get(key.removesuffix(":build-mismatch"), 0), count
                    )
    for name, count in sorted(mismatched.items()):
        notes.append(
            f"the {name} source disagreed with this reference on up to {count} record(s) "
            "per item: those records assert a base this genome does not have and were "
            "skipped, so the ancestry columns are that much closer to reference-only — a "
            "build mismatch, not an absence of population risk"
        )

    # A cohort is triaged by sorting a column, and `best_efficiency` is the column people
    # sort. When the rows' best candidates span chemistries, that sort compares a
    # base-editor number with a prime number — outputs of different, mutually
    # uncalibrated models. The single-variant menu states this in its rationale; the
    # surface built for sorting had nothing, which is the wrong way round.
    if len({r.get("best_chemistry") for r in rows if r.get("best_chemistry")}) > 1:
        notes.append(CROSS_CHEMISTRY_NOTE)

    return [note for note in notes if note]


def cohort_to_tsv(
    rows: list[dict[str, Any]],
    provenance: Any | None = None,
    *,
    counts: Mapping[str, int] | None = None,
) -> str:
    """Render the per-item summary rows as TSV (one row per cohort item).

    Led by the same `#` note block the per-design export carries: the research-use
    disclaimer, the coordinate convention, the reference genome's identity and the
    seed. This is the file a whole-cohort run is read through and the one that gets
    forwarded, and a row per patient with a bare `best_specificity` and no statement
    of which genome was searched is not interpretable.

    ``counts`` states what the run did, which matters most when it did nothing. A
    re-run against an existing manifest skips every item it has already designed, so
    `--summary-tsv` writes a well-formed table with a header and no rows — and a file
    with no rows reads as a cohort that produced no results. The terminal line was fixed
    for this once ("stating the requested count first stops `0 item(s)` from being the
    headline for a resume that had nothing left to do"); the file it writes says nothing,
    and the file is the half that outlives the terminal and gets forwarded.

    Args:
        rows: One summary dict per cohort item.
        provenance: The run's provenance block, if there is one, for the notes.
        counts: The run's ``total``/``succeeded``/``failed``/``skipped``, when known.

    Returns:
        The TSV text: `#` notes, the column header, one row per item.
    """
    notes = _cohort_notes(rows, provenance, counts)
    lines = [f"# {_cell(note)}" for note in notes]
    lines.append("\t".join(COHORT_COLUMNS))
    for r in rows:
        lines.append(
            "\t".join(
                _cell(_sources(r[c]) if c == "offtarget_sources" else r[c]) for c in COHORT_COLUMNS
            )
        )
    return "\n".join(lines) + "\n"


def cohort_to_parquet(
    rows: list[dict[str, Any]],
    path: str | Path,
    provenance: Any | None = None,
    *,
    counts: Mapping[str, int] | None = None,
) -> Path:
    """Write the per-item summary rows as Parquet — the same table the TSV holds.

    A cohort is the result that goes into a dataframe: hundreds of rows, one per
    patient, read by a pipeline rather than by eye. The single-design flat table had
    both encodings and this one had only the text form, which is the wrong way round —
    the per-candidate table is the one a human scrolls, and this is the one a pipeline
    loads.

    The columns and their order are :data:`COHORT_COLUMNS`, and the notes the TSV writes
    as leading ``#`` lines are written here as Parquet's file-level key/value metadata,
    for the reason the per-design writer records: a table of specificities with no
    statement of which genome was searched, under which seed, is not interpretable, and
    a format with somewhere to put that has no excuse for dropping it.

    Args:
        rows: One summary dict per cohort item, from :func:`cohort_rows`.
        path: Destination ``.parquet`` path.
        provenance: The run's provenance block, if there is one, for the notes.
        counts: The run's ``total``/``succeeded``/``failed``/``skipped``, when known.

    Returns:
        The written path.

    Raises:
        MissingDependencyError: If the optional ``polars`` dependency is absent.
    """
    from alleleforge.errors import MissingDependencyError

    try:
        import polars as pl
    except ImportError as exc:  # pragma: no cover - exercised only without polars
        raise MissingDependencyError(
            "Parquet export requires the optional 'polars' dependency (install alleleforge[core])"
        ) from exc

    dtypes = {bool: pl.Boolean, int: pl.Int64, float: pl.Float64, str: pl.Utf8}
    schema = {col: dtypes[COHORT_COLUMN_TYPES[col]] for col in COHORT_COLUMNS}
    frame = pl.DataFrame([_parquet_row(row) for row in rows], schema=schema)
    out = Path(path)
    # Zero-padded ordinals, because a Parquet reader gets a *mapping* and every one I
    # know sorts it, while the notes are an ordered document — disclaimer first, then
    # what was run, then what it read. The per-design writer learned this when adding a
    # note broke an alphabetical order that had matched by luck.
    frame.write_parquet(
        out,
        metadata={
            f"note_{index:02d}": note
            for index, note in enumerate(_cohort_notes(rows, provenance, counts), start=1)
        },
    )
    return out


def _parquet_row(row: dict[str, Any]) -> dict[str, Any]:
    """Project one summary row onto the typed columns Parquet declares.

    Numbers stay numbers — that is the point of having this encoding at all. The three
    structured columns are rendered exactly as the TSV renders them, including
    ``offtarget_sources``' "reference-only", so the two encodings do not disagree about
    the one field where "we did not look" must not read as "we looked and found nothing".
    """
    projected: dict[str, Any] = {}
    for column in COHORT_COLUMNS:
        value = row.get(column)
        if COHORT_COLUMN_TYPES[column] is not str or value is None:
            projected[column] = value
        elif column == "offtarget_sources":
            projected[column] = _cell(_sources(value))
        else:
            projected[column] = _cell(value)
    return projected
