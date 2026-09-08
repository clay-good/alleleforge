"""Machine-readable export of a design report: JSON, TSV, and Parquet.

There are two JSON forms and the difference matters. :func:`menu_to_json` writes the
:class:`~alleleforge.types.candidate.RankedMenu` and is the **lossless** one: everything
the design produced, including each candidate's full outcome spectrum and its off-target
site rows. :func:`report_to_json` writes the
:class:`~alleleforge.report.builder.DesignReport`, which is a *summary* — every candidate,
with counts and aggregates in place of those rows — so it is complete as a serialization
of the report and is not the place to look for detail the report withheld. Both validate
against the Phase 1 schemas. TSV is the flat, one-row-per-candidate form for
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
#: no comments does see; and for v11, when Parquet grew the same notes as file-level
#: key/value metadata; and for v13, when the notes grew the variant, the intent and the
#: ranking weights, and Parquet's metadata keys gained a `note_NN_` ordinal prefix so a
#: reader sorting them reads the notes in the order the document states them. That last
#: part is a BREAKING change to the Parquet metadata key names, taken pre-1.0 and with
#: the schema version bumped for exactly this purpose; and for v14, when
#: `bystander_burden` grew the interval and honesty flags its two neighbouring
#: predictions already carried.
EXPORT_SCHEMA_VERSION = 14

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
    # The same envelope `efficiency` above and `p_intended` below carry, on the third
    # calibrated `Prediction` in this row. It was the only one flattened to its point
    # estimate — the never-a-bare-float rule holding for two columns of a table and not
    # for the one between them.
    "bystander_burden_low",
    "bystander_burden_high",
    "bystander_burden_in_distribution",
    "bystander_burden_calibrated",
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
    # Empty unless the table mixes matrices: which one produced the worst score, the
    # number a reader acts on.
    "offtarget_worst_matrix",
    "offtarget_scorer_citation",
    "offtarget_search",
    "worst_ancestry",
    "worst_ancestry_score",
    "flags",
    # Ordering hazards found in the oligos themselves — an internal Type IIS site means
    # the cloning enzyme cuts the insert. They reach the HTML, the PDF and the JSON, and
    # not the table a pipeline filters on, which is the surface that places the order.
    # Empty when oligos were not requested, like every other conditional column.
    "oligo_warnings",
    # Which vector the oligos were built for, and the Type IIS enzyme its hazard screen
    # actually ran against. `oligo_warnings` is only interpretable against these: an
    # empty cell means "clean for *this* enzyme", and since the caller chooses the
    # vector — and an sgRNA-only choice leaves pegRNA rows on the pegRNA acceptor — one
    # table can carry rows screened by two different enzymes. The human renders name the
    # scheme on every candidate's block; the table a pipeline filters on did not.
    "oligo_scheme",
    "oligo_enzyme",
    # The hazard subset of `flags`, so a pipeline can filter on "needs attention"
    # without hard-coding which flag names are hazards — a list that grows.
    "caveats",
    "rationale",
    "reagent",
)

#: The type each flat column holds, for the formats that have types.
#:
#: Parquet inferred its schema from the rows, which is only sound when the first
#: `infer_schema_length` (100) of them are representative. On a real menu they are not:
#: `bystander_burden` is null for every prime candidate and a float on the one base
#: editor at rank 341, so a 341-row report died with a polars `ComputeError` — the
#: documented `--format parquet`, and `POST /api/design?format=parquet`, on an ordinary
#: mixed-chemistry design. Inference is wrong even when it works: a run with no
#: population data leaves `worst_ancestry` entirely null and gives it a Null dtype, so
#: two runs of the same tool write files a pipeline cannot union.
#:
#: Declared once and used for both the populated frame and the empty one, which is what
#: makes "the two flat formats hold the same table" true of the types as well as the
#: names.
TSV_COLUMN_TYPES: dict[str, type] = {
    "schema_version": int,
    "rank": int,
    "chemistry": str,
    "locus": str,
    "on_pareto_front": bool,
    "efficiency": float,
    "efficiency_low": float,
    "efficiency_high": float,
    "in_distribution": bool,
    "calibrated": bool,
    "bystander_burden": float,
    "bystander_burden_low": float,
    "bystander_burden_high": float,
    "bystander_burden_in_distribution": bool,
    "bystander_burden_calibrated": bool,
    "p_intended": float,
    "p_intended_low": float,
    "p_intended_high": float,
    "p_intended_in_distribution": bool,
    "p_intended_calibrated": bool,
    "n_offtarget_sites": int,
    "offtarget_specificity": float,
    "offtarget_expected_burden": float,
    "offtarget_scorer": str,
    "offtarget_matrix": str,
    "offtarget_worst_matrix": str,
    "offtarget_scorer_citation": str,
    "offtarget_search": str,
    "worst_ancestry": str,
    "worst_ancestry_score": float,
    "flags": str,
    "oligo_warnings": str,
    "oligo_scheme": str,
    "oligo_enzyme": str,
    "caveats": str,
    "rationale": str,
    "reagent": str,
}


def report_to_json(report: DesignReport, *, indent: int | None = 2) -> str:
    """Serialize the whole report to JSON: every field the report holds, nothing added.

    Not the lossless form of a *design*. The report is a summary — a candidate's outcome
    spectrum is truncated to `top_alleles` and its off-target sites are reduced to a
    count — and serializing it faithfully preserves the summary, not the detail. Use
    :func:`menu_to_json` for that; the renders say so where they withhold something.
    """
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
        "bystander_burden_low": None if burden is None else round(burden.interval[0], 4),
        "bystander_burden_high": None if burden is None else round(burden.interval[1], 4),
        "bystander_burden_in_distribution": None if burden is None else burden.in_distribution,
        "bystander_burden_calibrated": None if burden is None else burden.calibrated,
        "p_intended": None if candidate.p_intended is None else round(candidate.p_intended, 4),
        "p_intended_low": None if pi is None else round(pi.interval[0], 4),
        "p_intended_high": None if pi is None else round(pi.interval[1], 4),
        "p_intended_in_distribution": None if pi is None else pi.in_distribution,
        "p_intended_calibrated": None if pi is None else pi.calibrated,
        "n_offtarget_sites": candidate.n_offtarget_sites,
        # `None`, not `""`: the TSV renders both as an empty cell (`_cell`), and the
        # empty string made this the one numeric column carrying a string sentinel —
        # which a typed format cannot hold alongside the numbers it also carries.
        "offtarget_expected_burden": (
            None
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
        "offtarget_worst_matrix": candidate.offtarget_worst_matrix,
        "offtarget_scorer_citation": candidate.offtarget_scorer_citation,
        "offtarget_search": candidate.offtarget_search,
        "worst_ancestry": None if worst is None else worst.ancestry,
        "worst_ancestry_score": None if worst is None else round(worst.worst_score, 4),
        "flags": ";".join(candidate.flags),
        "oligo_warnings": ";".join(
            getattr(candidate.oligos, "warnings", ()) if candidate.oligos else ()
        ),
        # Empty together with `oligo_warnings` when no oligos were built, like every
        # other conditional column: no screen ran, so no enzyme cleared anything.
        "oligo_scheme": candidate.oligos.scheme.name if candidate.oligos else "",
        "oligo_enzyme": candidate.oligos.scheme.enzyme if candidate.oligos else "",
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

    The lines come from :func:`_export_notes`, shared with the Parquet writer, so the
    two flat formats cannot state different provenance for the same table.

    Args:
        report: The report being serialized.

    Returns:
        Comment lines, each already `#`-prefixed and free of tabs and newlines.
    """
    return [f"# {note}" for note in _export_notes(report).values()]


def _export_notes(report: DesignReport) -> dict[str, str]:
    """Return the notes that must accompany the flat table, as key/value pairs.

    The TSV carries these as `#` comment lines; Parquet carries them as file-level
    key/value metadata. Same facts, one source, because the two formats hold the same
    columns and a fact stated in one of them is not stated in the other.

    Args:
        report: The report being serialized.

    Returns:
        `disclaimer`, plus `provenance_1..n` in the order the renders print them.
    """
    notes: dict[str, str] = {}
    if report.disclaimer:
        notes["disclaimer"] = _cell(report.disclaimer)
    # What was asked for, and how the `rank` column was produced. `DesignReport` carries
    # nine fields; these notes were built from two of them, so the flat table — the one
    # format a scientist opens in a spreadsheet and forwards — was a list of reagents
    # with no statement of the variant they edit, the intent they were designed for, or
    # the weights that ordered them. Every one of the three is on the HTML and PDF header
    # line. `locus` per row names where a *guide* sits, which is not the same question.
    if report.variant:
        notes["variant"] = _cell(f"variant {report.variant}")
    if report.intent:
        notes["intent"] = _cell(f"intent {report.intent}")
    # What a clinical database asserts about that variant, when one was consulted. It is
    # the reason an accession is chosen over the coordinates it stands for, and the HTML
    # and PDF state it in the rationale — prose the flat table does not carry. A
    # spreadsheet of pegRNAs correcting a variant ClinVar calls Benign read exactly like
    # one correcting a pathogenic allele.
    if report.clinical_significance:
        notes["clinical_significance"] = _cell(f"ClinVar: {report.clinical_significance}")
    if report.weights:
        ordered = ", ".join(f"{name} {value:.2f}" for name, value in report.weights.items())
        notes["weights"] = _cell(f"ranking weights: {ordered}")
    for index, line in enumerate(provenance_lines(report.provenance), start=1):
        if line:
            notes[f"provenance_{index}"] = _cell(line)
    return notes


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
    # Projected onto TSV_COLUMNS, not left in `_row`'s dict order: the two orders had
    # already drifted apart by one adjacent swap, so `frame[:, 17]` was
    # `offtarget_expected_burden` in the Parquet and `offtarget_specificity` in the
    # TSV — two numbers on unrelated scales, in the pair of tables documented as
    # holding identical columns. It also makes the empty frame (built from the same
    # constant) and the populated one agree by construction rather than by luck.
    dtypes = {bool: pl.Boolean, int: pl.Int64, float: pl.Float64, str: pl.Utf8}
    schema = {col: dtypes[TSV_COLUMN_TYPES[col]] for col in TSV_COLUMNS}
    frame = pl.DataFrame(rows, schema=schema)
    out = Path(path)
    # Zero-padded ordinals, because a Parquet reader gets a *mapping* and every one I
    # know sorts it. The notes are an ordered document — disclaimer, what was asked for,
    # how it was ranked, then provenance — and until v13 the alphabetical order happened
    # to match the document order by luck (`disclaimer` < `provenance_*`). Adding
    # `variant`/`intent`/`weights` broke the coincidence, which is the guard doing its
    # job. Prefixing makes the order a property of the format rather than of the words.
    ordered = {
        f"note_{index:02d}_{key}": value
        for index, (key, value) in enumerate(_export_notes(report).items(), start=1)
    }
    frame.write_parquet(out, metadata=ordered)
    return out
