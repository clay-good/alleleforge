"""Which parts of a candidate the flat table drops, and why — written down.

`_row` and `TSV_COLUMNS` are hand-written, so a field added to `CandidateReport` reaches
the HTML, the PDF and the report JSON automatically and the flat exports never. The
cohort's row/TSV pair had exactly that gap and it cost a column; this is the same pair one
level up, and it had no check at all.

Most of the flattening is deliberate and good: a `Prediction` becomes a value plus its
interval and its two honesty flags, a list of ancestry rows becomes the worst one. That is
what a flat table is *for*. The point is not to forbid it but to make each decision a
recorded one, so the next field added is either flattened on purpose or noticed.

Following the project's own precedent: writing down why something is exempt is worth more
than finding the fifth instance of it.
"""

from __future__ import annotations

from alleleforge.report.builder import CandidateReport
from alleleforge.report.export import TSV_COLUMNS

#: Fields the flat table carries under other names, mapped to the columns that carry
#: them. Flattening is the table's job; losing track of what was flattened is not.
_FLATTENED: dict[str, tuple[str, ...]] = {
    "efficiency": (
        "efficiency",
        "efficiency_low",
        "efficiency_high",
        "in_distribution",
        "calibrated",
    ),
    "bystander_burden": (
        "bystander_burden",
        "bystander_burden_low",
        "bystander_burden_high",
        "bystander_burden_in_distribution",
        "bystander_burden_calibrated",
    ),
    "p_intended_prediction": (
        "p_intended_low",
        "p_intended_high",
        "p_intended_in_distribution",
        "p_intended_calibrated",
    ),
    "offtarget_by_ancestry": ("worst_ancestry", "worst_ancestry_score"),
    "oligos": ("oligo_warnings", "oligo_scheme", "oligo_enzyme"),
    "flags": ("flags", "caveats"),
}

#: Fields the flat table deliberately does not carry, each with the reason.
_NOT_IN_THE_FLAT_TABLE: dict[str, str] = {
    "outcome_top": "a per-candidate list of alleles; one row per candidate cannot hold "
    "a nested table, and `--json` is documented as the surface that carries it",
    "outcome_shown_mass": "states what fraction of the distribution `outcome_top` shows, "
    "and this table shows no alleles at all — the number would qualify nothing here",
    "n_outcome_alleles": "the size of that same distribution; `p_intended` with its "
    "interval is what a flat row carries about the outcome",
    "oligos_requested": "whether oligos were asked for, which the three `oligo_*` "
    "columns already answer: all three empty means none were built",
}


def test_every_candidate_field_is_carried_or_excused() -> None:
    columns = set(TSV_COLUMNS)
    unaccounted = sorted(
        name
        for name in CandidateReport.model_fields
        if name not in columns and name not in _FLATTENED and name not in _NOT_IN_THE_FLAT_TABLE
    )
    assert not unaccounted, (
        f"`CandidateReport` gained {unaccounted} and the flat exports carry nothing for "
        "them. Add a column, record the columns it flattens into in _FLATTENED, or "
        "record why the table cannot hold it in _NOT_IN_THE_FLAT_TABLE."
    )


def test_the_flattening_map_names_real_columns() -> None:
    """An entry claiming a field is carried must name columns that exist."""
    columns = set(TSV_COLUMNS)
    for field, carriers in _FLATTENED.items():
        missing = sorted(set(carriers) - columns)
        assert not missing, f"{field} is recorded as flattened into missing columns: {missing}"


def test_the_allowances_name_real_fields() -> None:
    """An excuse must not outlive the field it excuses."""
    fields = set(CandidateReport.model_fields)
    stale = sorted((set(_FLATTENED) | set(_NOT_IN_THE_FLAT_TABLE)) - fields)
    assert not stale, f"recorded for fields `CandidateReport` no longer has: {stale}"


def test_no_field_is_both_carried_and_excused() -> None:
    """The stronger form: an excuse for something the table does carry is a false record."""
    both = sorted(set(_NOT_IN_THE_FLAT_TABLE) & (set(TSV_COLUMNS) | set(_FLATTENED)))
    assert not both, f"excused but carried: {both}. Drop the entry."


def test_every_column_traces_to_something() -> None:
    """The other direction: a column no field feeds is an always-empty one."""
    fields = set(CandidateReport.model_fields)
    carried = {column for carriers in _FLATTENED.values() for column in carriers}
    #: Columns the writer adds itself rather than reading off a candidate.
    added_by_the_writer = {"schema_version"}
    orphans = sorted(set(TSV_COLUMNS) - fields - carried - added_by_the_writer)
    assert not orphans, (
        f"columns that trace to no `CandidateReport` field: {orphans}. Either the field "
        "was renamed and the column left behind, or _FLATTENED should record the link."
    )
