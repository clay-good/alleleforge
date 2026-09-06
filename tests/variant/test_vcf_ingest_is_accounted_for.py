"""A VCF row that becomes no design request must be counted, not just dropped.

`_split_record` drops three kinds of row, all of them correctly -- none names a
designable substitution:

* a soft-filtered call (`FILTER` is not PASS), skipped by default;
* a row whose REF is symbolic or not ACGTN;
* a symbolic ALT: `<DEL>`, `<DUP>`, a breakend, or the `*` spanning-deletion allele.

A real VCF carries all three routinely. Dropping them silently means the cohort is
smaller than the file, the run reports success, and nothing anywhere connects the two
numbers -- the same shape as every other finding in this log, pointed the same way:
fewer variants is a shorter list, a faster run, and no complaint.

The subtle case is a multi-allelic row that loses one ALT and keeps another. It is not
"a row that yielded nothing", which is why the summary counts *drops* rather than rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from alleleforge.variant.vcf import (
    SKIP_NOT_PASS,
    SKIP_SYMBOLIC_ALT,
    SKIP_SYMBOLIC_REF,
    VcfIngestCounts,
    iter_vcf,
)


@dataclass
class Row:
    """A duck-typed cyvcf2 ``Variant``, the shape `iter_vcf` accepts directly."""

    CHROM: str
    POS: int
    REF: str
    ALT: list[str] = field(default_factory=list)
    FILTER: str | None = None
    ID: str | None = None


def _counted(rows: list[Row]) -> tuple[list[object], VcfIngestCounts]:
    counts = VcfIngestCounts()
    return list(iter_vcf(rows, counts=counts)), counts


def test_a_clean_vcf_reports_nothing() -> None:
    """A caveat that fires always is a caveat nobody reads."""
    records, counts = _counted([Row("chr1", 100, "A", ["G"]), Row("chr1", 200, "C", ["T"])])

    assert len(records) == 2
    assert counts.rows == 2
    assert counts.records == 2
    assert counts.skipped == {}
    assert counts.summary() == ""


def test_each_drop_reason_is_counted_separately() -> None:
    """The reasons have different remedies, so one number would not be actionable."""
    _, counts = _counted(
        [
            Row("chr1", 100, "A", ["G"]),
            Row("chr1", 200, "A", ["G"], FILTER="LowQual"),
            Row("chr1", 300, "<INS>", ["A"]),
            Row("chr1", 400, "A", ["<DEL>"]),
            Row("chr1", 500, "A", ["*"]),
        ]
    )

    assert counts.skipped[SKIP_NOT_PASS] == 1
    assert counts.skipped[SKIP_SYMBOLIC_REF] == 1
    assert counts.skipped[SKIP_SYMBOLIC_ALT] == 2  # <DEL> and *
    assert counts.total_skipped == 4


def test_a_partly_dropped_multiallelic_row_is_not_called_empty() -> None:
    """The row a reader most needs to know about: it came through *incomplete*.

    One ALT designable, one symbolic. Counting rows rather than drops would either
    report it as a clean row or as a lost one, and it is neither.
    """
    records, counts = _counted([Row("chr1", 400, "A", ["<DUP>", "T"])])

    assert counts.rows == 1
    assert counts.records == 1
    assert counts.skipped == {SKIP_SYMBOLIC_ALT: 1}
    assert [r.alt for r in records] == ["T"]  # type: ignore[attr-defined]
    assert "1 VCF row(s) yielded 1 design request(s)" in counts.summary()


def test_the_summary_states_the_consequence_not_only_the_count() -> None:
    _, counts = _counted([Row("chr1", 200, "A", ["G"], FILTER="LowQual")])

    summary = counts.summary()
    assert "1 drop(s)" in summary
    assert SKIP_NOT_PASS in summary
    assert "smaller than the file" in summary


def test_counting_is_optional_and_changes_nothing() -> None:
    """The counter is an observer: the records yielded must not depend on it."""
    rows = [
        Row("chr1", 100, "A", ["G"]),
        Row("chr1", 200, "A", ["G"], FILTER="LowQual"),
        Row("chr1", 400, "A", ["<DUP>", "T"]),
    ]
    with_counts, _ = _counted(rows)
    without = list(iter_vcf(rows))

    assert [(r.chrom, r.pos, r.alt) for r in without] == [  # type: ignore[attr-defined]
        (r.chrom, r.pos, r.alt)
        for r in with_counts  # type: ignore[attr-defined]
    ]


def test_pass_only_disabled_keeps_the_soft_filtered_call() -> None:
    """Guard the guard: the counter must track the option, not a fixed assumption."""
    counts = VcfIngestCounts()
    records = list(
        iter_vcf([Row("chr1", 200, "A", ["G"], FILTER="LowQual")], pass_only=False, counts=counts)
    )

    assert len(records) == 1
    assert SKIP_NOT_PASS not in counts.skipped
