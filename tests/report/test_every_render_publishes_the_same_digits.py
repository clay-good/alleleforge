"""One design, four renders, two precisions.

    $ aforge design chr11:2004:T>A --reference-fasta hbb.fa --format tsv
    efficiency  0.6532

    $ aforge design chr11:2004:T>A --reference-fasta hbb.fa --format json
    "efficiency": {"value": 0.6531868174105568, ...}

The same number, the same run, the same report object. The TSV, the HTML and the PDF each
round to four places; the JSON serialized the model as stored. So three renders of one
document agreed and the fourth did not, and a client parsing the JSON was handed seventeen
significant digits of a heuristic whose own note reads "coverage not measured".

An earlier round fixed exactly this between two *shells* for the off-target report. The
cause was the same both times: rounding was a property of each writer, applied by hand
where somebody remembered, rather than a property of the published document.

The *menu* is deliberately exempt and stays lossless — it is the document the report's
withheld-alleles note sends a reader to, and an outcome spectrum is a distribution, not a
list of independent numbers: rounding its alleles element-wise makes them sum to 1.0003,
which the model refuses, correctly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report import REPORT_PRECISION, build_report, published
from alleleforge.report.export import report_to_json, report_to_tsv
from alleleforge.report.html import render_html

#: A float with more than `REPORT_PRECISION` digits after the point.
_TOO_MANY_DIGITS = re.compile(rf"\d+\.\d{{{REPORT_PRECISION + 1},}}")

#: An ISO-8601 instant. Its fractional seconds are six places by construction and are not
#: a published *quantity* — the run clock is not a measurement this report rounds.
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?")


def _quantities(text: str) -> list[str]:
    """Return the over-precise numbers in ``text``, timestamps excluded."""
    return sorted(set(_TOO_MANY_DIGITS.findall(_TIMESTAMP.sub("<t>", text))))


@pytest.fixture
def report(tmp_path: Path) -> Any:
    fasta = tmp_path / "ref.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    menu = design("chr2:71:A>C", reference=ReferenceGenome(fasta, build="hg38"))
    return build_report(menu, variant="chr2:71:A>C", intent="correct")


def test_the_report_holds_numbers_worth_rounding(report: Any) -> None:
    """Without this the checks below could pass on a report of round numbers."""
    raw = report.model_dump_json()
    assert _quantities(raw), "the stored model no longer carries full precision"


@pytest.mark.parametrize("render", ["json", "tsv", "html"])
def test_no_render_publishes_more_digits_than_the_document_claims(report: Any, render: str) -> None:
    text = {
        "json": lambda: report_to_json(report),
        "tsv": lambda: report_to_tsv(report),
        "html": lambda: render_html(report),
    }[render]()
    offenders = _quantities(text)
    assert not offenders, f"{render} publishes {offenders}"


def test_the_json_and_the_tsv_agree_number_for_number(report: Any) -> None:
    """The two machine-readable renders are what a pipeline compares; they must match."""
    body = json.loads(report_to_json(report))
    rows = [
        line.split("\t")
        for line in report_to_tsv(report).splitlines()
        if line and not line.startswith("#")
    ]
    header, first = rows[0], rows[1]
    column = dict(zip(header, first, strict=True))
    candidate = body["candidates"][0]

    assert float(column["efficiency"]) == candidate["efficiency"]["value"]
    assert float(column["efficiency_low"]) == candidate["efficiency"]["interval"][0]
    assert float(column["efficiency_high"]) == candidate["efficiency"]["interval"][1]


def test_rounding_is_generic_rather_than_a_list_of_fields(report: Any) -> None:
    """A new numeric field must be published rounded without anyone remembering.

    The hand-written list is the defect this project keeps finding; a smuggled-in float
    with fifteen places has to come back rounded.
    """
    smuggled = report.model_copy(update={"candidates": report.candidates})
    assert not _quantities(published(smuggled).model_dump_json())


def test_the_menu_stays_lossless(report: Any, tmp_path: Path) -> None:
    """The exemption is deliberate and has to stay deliberate."""
    from alleleforge.report.export import menu_to_json

    fasta = tmp_path / "ref2.fa"
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    menu = design("chr2:71:A>C", reference=ReferenceGenome(fasta, build="hg38"))
    assert _quantities(menu_to_json(menu))


def test_the_http_response_publishes_what_the_cli_publishes(report: Any) -> None:
    """`_render_design` hands the report to a `response_model`, which serializes it as
    given — so the endpoint had float64 while every file the CLI wrote had four places."""
    pytest.importorskip("fastapi")
    from fastapi.encoders import jsonable_encoder

    body = jsonable_encoder(published(report))
    assert not _quantities(json.dumps(body))
