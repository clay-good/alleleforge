"""A placeholder is an input, and the only way to check an input is to submit it.

The page's variant box read `chr2:71:A>C · 2 71 . A C`. A previous round checked that no
placeholder offers a form this deployment *refuses* — a check on the shape of the string —
and the second half of that placeholder answered `unrecognized variant input` for as long
as it had been there, because nothing ever typed it.

Every doc guard in this repository checks that a **name** exists: a flag, a command, a
module path, a link. A placeholder is not a name. So this one submits them: every example
the page shows in an input whose `name` matches a request field is posted to the endpoint
that field belongs to, and must be answered.

The population comes from the page (`placeholder=` beside `name=`), so a new example box
is covered the day it is added — and the `·`/newline separators the page uses to show
several forms in one placeholder are split, because each of them is an example a reader
will copy on its own.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

_INDEX = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "index.html"
).read_text(encoding="utf-8")

#: The input names this file knows how to submit, and how. Anything else on the page is
#: skipped — and the floor below refuses a run where *nothing* was submitted, so a rename
#: that empties this cannot pass quietly.
_SUBMIT = {
    "variant": lambda value: ("/api/resolve", {"variant": value}),
    "variants": lambda value: ("/api/batch", {"variants": [value], "run_offtarget": False}),
    "spacer": lambda value: (
        "/api/offtarget",
        {"spacer": value, "mismatches": 2, "dna_bulges": 0, "rna_bulges": 0},
    ),
}


def _examples() -> list[tuple[str, str]]:
    """Return (input name, example) for every placeholder in a submittable input."""
    found: list[tuple[str, str]] = []
    for tag in re.findall(r"<(?:input|textarea)[^>]*>", _INDEX):
        name = re.search(r'name="([^"]+)"', tag)
        placeholder = re.search(r'placeholder="([^"]*)"', tag)
        if name is None or placeholder is None or name.group(1) not in _SUBMIT:
            continue
        text = html.unescape(placeholder.group(1))
        for example in re.split(r"\s+·\s+|\n", text):
            if example.strip():
                found.append((name.group(1), example.strip()))
    return found


#: What a *parse* failure says. The page's examples name loci in a real genome, which no
#: test fixture holds, so "this reference does not have chr7:117,559,590" is an honest
#: answer to an example and "I cannot read `2 71 . A C`" is not. That distinction is the
#: whole check: a form the API cannot parse is a form no reader can use anywhere.
_UNPARSEABLE = ("unrecognized variant input", "not a designable substitution")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """A small deployment. The examples' loci are real-genome loci; their *forms* are not."""
    import random

    random.seed(3)
    fasta = tmp_path / "page.fa"
    fasta.write_text(">chr2\n" + "".join(random.choice("ACGT") for _ in range(400)) + "\n")
    return TestClient(create_app(reference=ReferenceGenome(fasta, build="hg38")))


def test_the_page_offers_examples_to_check() -> None:
    examples = _examples()
    assert len(examples) >= 4, examples
    assert any(name == "variant" for name, _ in examples)
    assert any(" " in value for _, value in examples), (
        "no whitespace-separated example found — the VCF-record form this file was "
        "written for is the one that went unchecked"
    )


@pytest.mark.parametrize(("name", "example"), _examples(), ids=lambda v: str(v)[:40])
def test_an_example_the_page_shows_is_a_form_the_api_can_read(
    client: TestClient, name: str, example: str
) -> None:
    path, payload = _SUBMIT[name](example)
    response = client.post(path, json=payload)
    assert response.status_code < 500, (name, example, response.text)
    body = response.text
    # A cohort answers 200 with per-row errors, so the rows are read as well as the status.
    for unreadable in _UNPARSEABLE:
        assert unreadable not in body, (
            f"the page offers {example!r} in its {name!r} box and the API cannot read it: "
            f"{body[:300]}"
        )
