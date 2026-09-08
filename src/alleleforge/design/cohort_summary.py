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
from typing import Any

from alleleforge._version import __version__

__all__ = ["cohort_reference_shape_suffix", "cohort_rows", "cohort_to_tsv"]


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
                "best_chemistry": summary.get("best_chemistry"),
                "best_efficiency": summary.get("best_efficiency"),
                "best_efficiency_low": summary.get("best_efficiency_low"),
                "best_efficiency_high": summary.get("best_efficiency_high"),
                "best_efficiency_in_distribution": summary.get("best_efficiency_in_distribution"),
                "best_caveats": summary.get("best_caveats") or [],
                "best_bystander_burden": summary.get("best_bystander_burden"),
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
    cols = [
        "item_id",
        "variant",
        "status",
        "best_chemistry",
        "best_efficiency",
        "best_efficiency_low",
        "best_efficiency_high",
        "best_efficiency_in_distribution",
        "best_caveats",
        "offtarget_sources",
        "best_bystander_burden",
        "worst_offtarget",
        "best_specificity",
        "n_candidates",
        "no_candidate_reason",
        "error",
    ]

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
    # A cohort is triaged by sorting a column, and `best_efficiency` is the column people
    # sort. When the rows' best candidates span chemistries, that sort compares a
    # base-editor number with a prime number — outputs of different, mutually
    # uncalibrated models. The single-variant menu states this in its rationale; the
    # surface built for sorting had nothing, which is the wrong way round.
    if len({r.get("best_chemistry") for r in rows if r.get("best_chemistry")}) > 1:
        notes.append(CROSS_CHEMISTRY_NOTE)

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

    lines = [f"# {_cell(note)}" for note in notes if note]
    lines.append("\t".join(cols))
    for r in rows:
        lines.append(
            "\t".join(_cell(_sources(r[c]) if c == "offtarget_sources" else r[c]) for c in cols)
        )
    return "\n".join(lines) + "\n"
