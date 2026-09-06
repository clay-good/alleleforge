"""A requested ancestry with nothing behind it must be named *in the artifact*.

`--populations` names the labels to stratify by; it supplies no alleles. Asked for three
ancestries with no `--gnomad` and no `--haplotypes`, the scan is reference-only and the
breakdown comes back empty -- which, as the CLI's own warning puts it, "reads like 'no
ancestry-specific risk found' rather than 'nothing was searched'."

That warning went to the terminal. `unbacked_populations`, the field that carries the
same fact into the HTML page, the printable PDF and the TSV export, was computed with a
trailing `if backed else ()` that switched it off in exactly this case -- deliberately,
on the reasoning that the CLI warned separately. So the durable artifact a collaborator
is handed said nothing, and a library or web caller was told nothing at all:

    requested populations : ['afr', 'eas', 'sas']
    unbacked_populations  : ()
    ancestry breakdown    : {}

Three ancestries requested, an empty breakdown, and no statement anywhere in the report
that the request went unhonored. The two cases -- no source, and a source that lacks the
label -- differ in how a user fixes them, not in what the report has to say.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

from .conftest import PAD, SPACER

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
REQUESTED = ["afr", "eas", "sas"]


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + PAD + SPACER + "CGG" + PAD + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_ancestries_requested_with_no_source_at_all_are_named(
    reference: ReferenceGenome,
) -> None:
    report = search(SPACER, PAM(pattern="NGG"), reference=reference, populations=REQUESTED)
    assert report.unbacked_populations == tuple(REQUESTED), (
        "a reference-only scan reports an empty ancestry breakdown; without naming the "
        "requested labels it reads as 'no ancestry-specific risk found'"
    )


def test_the_statement_reaches_the_search_description(reference: ReferenceGenome) -> None:
    """That description is what the HTML, the PDF and the TSV all carry."""
    report = search(SPACER, PAM(pattern="NGG"), reference=reference, populations=REQUESTED)
    description = report.search_description()
    for population in REQUESTED:
        assert population in description, description
    assert "requested but not examined" in description
    assert "'no data', not 'no risk'" in description


def test_requesting_nothing_reports_nothing(reference: ReferenceGenome) -> None:
    """Guard the guard: the field must stay empty when no ancestry was asked for.

    Otherwise every reference-only scan would grow a warning about labels the user
    never requested, and a caveat that fires always is a caveat nobody reads.
    """
    report = search(SPACER, PAM(pattern="NGG"), reference=reference)
    assert report.unbacked_populations == ()
    assert "requested but not examined" not in report.search_description()
