"""The printable sheet's rules and separators are its structure, and nothing read them.

A statement-deletion sweep removed eleven `lines.append(...)` / `parts.append(...)` calls
from `report/pdf.py` one at a time and the whole suite stayed green for every one: the
`=` rule under the title, both `-` rules around the candidate list, six of the blank
lines that separate the sheet's blocks, the blank line that ends each candidate, and the
`ET` operator that closes a page's text object.

The existing pdf tests are thorough about two things — that a line fits the column, and
that a sequence run is not divided — and about *facts*: this field is present, that
disclaimer is there. Every one of them passes on a sheet whose blocks have run together,
because the strings they look for are all still in it. A leave-behind someone reads at a
bench is one where `ABOUT THIS RUN, NOT ABOUT A CANDIDATE` sits hard against the last
line of the block above it, under no rule, with the candidates below it in the same
undifferentiated column.

`ET` is worse than cosmetic. A content stream that opens `BT` and never closes it is not
a valid PDF text object; the extractor this suite uses reads it anyway, which is exactly
why nothing noticed.
"""

from __future__ import annotations

import pytest

from alleleforge.report.builder import build_report
from alleleforge.report.pdf import _content_stream, _paginate, _report_lines, _rule, render_pdf

_HEADINGS = (
    "RESEARCH USE ONLY",
    "PART OF THIS MENU IS MISSING",
    "ABOUT THIS RUN, NOT ABOUT A CANDIDATE",
    "HOW THIS MENU WAS ASSEMBLED",
    "PROVENANCE",
    "MODEL LIMITATIONS",
)


@pytest.fixture
def lines(prime_menu: object) -> list[str]:
    return _report_lines(build_report(prime_menu), None)  # type: ignore[arg-type]


def test_the_title_sits_above_a_rule(lines: list[str]) -> None:
    """The one line that says where the heading ends and the sheet begins."""
    rule = _rule("=")
    assert rule in lines, "the sheet has no heading rule at all"
    assert lines.index(rule) == 1, lines[:3]


def test_the_candidate_list_is_bracketed_by_rules(lines: list[str]) -> None:
    """Two rules, one each side, and the suite had no case for either."""
    rule = _rule("-")
    heading = next(i for i, line in enumerate(lines) if line.startswith("Candidates ("))
    assert lines[heading + 1] == rule, lines[heading : heading + 2]
    assert lines.count(rule) >= 2, "the candidate list is not closed by a rule"
    assert lines.index(rule, heading + 2) > heading, "no rule after the candidates"


@pytest.mark.parametrize("heading", _HEADINGS)
def test_every_block_heading_starts_on_a_blank_line(lines: list[str], heading: str) -> None:
    """A heading jammed under the block above it is not a heading."""
    at = [i for i, line in enumerate(lines) if line.strip() == heading]
    if not at:
        pytest.skip(f"this fixture produces no {heading!r} block")
    for i in at:
        previous = lines[i - 1]
        assert previous.strip() == "" or previous in (_rule("-"), _rule("=")), (
            f"{heading!r} follows {previous!r}"
        )


def test_the_sheet_separates_its_leading_blocks(lines: list[str]) -> None:
    """The disclaimer, the variant line and the weights are three blocks, not one."""
    variant = next(i for i, line in enumerate(lines) if line.startswith("Variant:"))
    assert lines[variant - 1] == "", lines[variant - 2 : variant + 1]


def test_every_candidate_block_is_closed(prime_menu: object) -> None:
    """Each candidate ends on a blank line, or the next one begins on its last."""
    from alleleforge.report.pdf import _candidate_lines

    report = build_report(prime_menu)  # type: ignore[arg-type]
    assert report.candidates, "no candidate; this check would be vacuous"
    for candidate in report.candidates:
        assert _candidate_lines(candidate)[-1] == "", candidate.reagent


def test_every_page_closes_the_text_object_it_opens(lines: list[str]) -> None:
    """`BT` without `ET` is not a valid text object, whatever an extractor tolerates."""
    pages = _paginate(list(lines))
    assert pages, "the sheet produced no pages"
    for number, page in enumerate(pages):
        stream = _content_stream(page).decode("cp1252")
        assert stream.count("BT") == 1, (number, stream[:60])
        assert stream.count("ET") == 1, (number, stream[-60:])
        assert stream.rstrip().endswith("ET"), (number, stream[-60:])


def test_the_rendered_pdf_closes_every_text_object(prime_menu: object) -> None:
    """And the same claim on the bytes a reader actually receives."""
    pdf = render_pdf(build_report(prime_menu))  # type: ignore[arg-type]
    text = pdf.decode("cp1252", "replace")
    assert text.count("BT ") == text.count("ET"), (text.count("BT "), text.count("ET"))


@pytest.fixture
def full_lines(prime_menu: object) -> list[str]:
    """A sheet carrying every optional block, which the menu fixture does not produce.

    Three of the sheet's blocks are conditional — the missing-chemistry list, the
    run-level notes, and the assembly rationale — and each ends on a blank line that
    separates it from whatever heading comes next. A report without them never runs
    those statements, so their separators cannot be measured on the ordinary fixture:
    the deletions stayed alive not because nothing checked, but because nothing in the
    suite had a sheet shaped like a real one.
    """
    report = build_report(prime_menu)  # type: ignore[arg-type]
    return _report_lines(
        report.model_copy(
            update={
                "unavailable": ("base_abe: the store this run was told to reuse is altered",),
                "notes": ("the gnomAD release supplied covers no contig in this reference",),
                "rationale": "Routing: prime=yes.\nEligible and run: prime.",
            }
        ),
        None,
    )


def test_the_full_sheet_carries_every_optional_block(full_lines: list[str]) -> None:
    """The premise for the separators below."""
    for heading in (
        "PART OF THIS MENU IS MISSING",
        "ABOUT THIS RUN, NOT ABOUT A CANDIDATE",
        "HOW THIS MENU WAS ASSEMBLED",
    ):
        assert any(line.strip() == heading for line in full_lines), heading


@pytest.mark.parametrize(
    "heading",
    [
        "PART OF THIS MENU IS MISSING",
        "ABOUT THIS RUN, NOT ABOUT A CANDIDATE",
        "HOW THIS MENU WAS ASSEMBLED",
        "Candidates (",
    ],
)
def test_every_block_on_a_full_sheet_starts_on_a_blank_line(
    full_lines: list[str], heading: str
) -> None:
    """Each conditional block closes itself, so the next one begins on clear ground."""
    at = [i for i, line in enumerate(full_lines) if line.strip().startswith(heading)]
    assert at, heading
    for i in at:
        assert full_lines[i - 1].strip() == "", f"{heading!r} follows {full_lines[i - 1]!r}"


def test_a_capped_sheet_separates_its_withheld_note_from_the_first_candidate(
    prime_menu: object,
) -> None:
    """The last conditional block, which needs a cap to exist at all.

    When `--max-candidates` withholds rows the sheet says so, in a sentence that ends
    by naming where the rest went. Without its closing blank line the first candidate's
    heading begins on the line below that sentence and reads as part of it.
    """
    report = build_report(prime_menu)  # type: ignore[arg-type]
    if len(report.candidates) < 2:
        pytest.skip("this fixture produces too few candidates to withhold any")
    lines = _report_lines(report, 1)
    at = next(i for i, line in enumerate(lines) if line.strip().startswith("Showing 1 of "))
    tail = at
    while tail + 1 < len(lines) and lines[tail + 1].strip() and not lines[tail + 1].startswith("#"):
        if lines[tail + 1].strip().startswith("Showing"):
            break
        tail += 1
    assert lines[tail + 1] == "", (lines[at : tail + 3],)
