"""The empty spacer, and the fields the two shells disagreed about.

`POST /api/offtarget {"spacer": ""}` answered **200** with a full report: thousands of
"off-target sites", worst score 1.000, specificity 0.000. Every position of a genome
matches an empty query. Round 523 chose to *label* a too-short spacer rather than refuse it
— screening a seed sequence is a legitimate thing to ask for — but an empty one is not that:
there is nothing to screen, and no caveat makes that report mean anything. It is refused, at
the library's one door, so both shells get it.

The other half is a parity gap this project's own previous round opened. The CLI learned to
refuse `--cell-context ""` because `value or default` cannot tell an empty string from an
omitted flag. The web models had the identical hole and no check: `{"cell_context": ""}`
answered 200 with a design whose out-of-distribution flag could never be raised, and
`{"populations": [""]}` answered 200 with no population analysis. A client that JSON-encodes
an unfilled form field is the browser's version of an unset shell variable.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("spacer", ["", "   ", "\t"])
async def test_an_empty_spacer_is_not_a_query(client: Any, spacer: str) -> None:
    response = await client.post("/api/offtarget", json={"spacer": spacer})
    assert response.status_code == 422, response.text
    detail = str(response.json()["detail"])
    assert "nothing to search for" in detail
    # The number the old 200 reported is named, so a reader who saw it knows what it was.
    assert "specificity" in detail


async def test_a_short_spacer_is_still_answered(client: Any) -> None:
    """Refusing the empty case must not undo round 523's deliberate choice to label."""
    response = await client.post("/api/offtarget", json={"spacer": "ACGT"})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "body",
    [
        {"variant": "chr2:71:A>C", "cell_context": ""},
        {"variant": "chr2:71:A>C", "cell_context": "  "},
        {"variant": "chr2:71:A>C", "populations": [""]},
        {"variant": "chr2:71:A>C", "chemistries": [""]},
        {"variant": "chr2:71:A>C", "intent": ""},
    ],
)
async def test_a_blank_field_is_refused_as_the_cli_refuses_it(
    client: Any, body: dict[str, Any]
) -> None:
    response = await client.post("/api/design", json=body)
    assert response.status_code == 422, response.text
    detail = str(response.json()["detail"])
    assert "sent empty" in detail or "names nothing" in detail


async def test_omitting_the_field_is_still_the_way_to_take_the_default(client: Any) -> None:
    """The remedy the message gives has to work."""
    response = await client.post("/api/design", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("field", ["populations", "chemistries"])
async def test_a_stray_comma_in_a_list_is_not_a_refusal(client: Any, field: str) -> None:
    """`afr,,eas` is the commonest typo in a comma-separated list, and the CLI has always
    dropped the empty element and run. Applying the scalar rule element-wise made the
    served page refuse it — its own parser trims each entry and keeps the empty one,
    posting `["afr", "", "eas"]` — so the check written to stop two shells disagreeing
    made them disagree the other way round. Found by typing it into the page.
    """
    values = {"populations": ["afr", "", "eas"], "chemistries": ["prime", ""]}[field]
    response = await client.post("/api/design", json={"variant": "chr2:71:A>C", field: values})
    assert response.status_code == 200, response.text


async def test_a_list_of_nothing_but_blanks_is_still_refused(client: Any) -> None:
    """That *is* the scalar mistake: the field was filled in with commas and no labels."""
    response = await client.post(
        "/api/design", json={"variant": "chr2:71:A>C", "populations": ["", "  "]}
    )
    assert response.status_code == 422, response.text
    assert "names nothing" in str(response.json()["detail"])
