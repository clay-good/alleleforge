"""The report told a browser user to run a terminal command.

Every truncated outcome table carries the same sentence: *"showing 3 of 4 predicted
alleles … the full spectrum is on the ranked menu, not in the report export — `aforge
design --json` writes it."* That sentence is rendered into the HTML the served page
displays — to the audience the page exists for, described in the README as "users who will
not touch a terminal".

And no HTTP route returned the menu. Not `/api/design` in any `format`, not the async job
result: every one is built from a `DesignReport`, which is where the truncation happens.
The page's "Download JSON" gave `outcome_top: 3` of `n_outcome_alleles: 4`. The library had
the whole thing all along.

Which byproducts a pegRNA produces is the question an outcome table exists to answer, and
the allele withheld from this fixture is an `indel`.

`format=menu` returns the ranked menu, and the page has a button for it. The two documents
stay distinct on purpose — the report is the richer *presentation* (it carries the intent,
the weights, the rendered rationale), the menu the richer *data* — which is why this is a
second download rather than a change to the first.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_the_report_format_still_truncates(client: httpx.AsyncClient) -> None:
    """The premise. Without a withheld allele the rest of this file proves nothing."""
    response = await client.post("/api/design?format=json", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 200, response.text
    candidate = response.json()["candidates"][0]
    assert candidate["n_outcome_alleles"] > len(candidate["outcome_top"]), candidate


@pytest.mark.anyio
async def test_the_menu_format_carries_every_allele(client: httpx.AsyncClient) -> None:
    report = (await client.post("/api/design?format=json", json={"variant": "chr2:71:A>C"})).json()
    response = await client.post("/api/design?format=menu", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")

    menu = response.json()
    candidate = menu["candidates"][0]
    assert "outcome" in candidate, sorted(candidate)
    alleles = candidate["outcome"]["alleles"]
    assert len(alleles) == report["candidates"][0]["n_outcome_alleles"], alleles

    shown = {a["allele"] for a in report["candidates"][0]["outcome_top"]}
    assert {a["allele"] for a in alleles} - shown, "the menu showed no more than the report"


@pytest.mark.anyio
async def test_the_menu_is_the_menu_and_not_the_report(client: httpx.AsyncClient) -> None:
    """A response model that reshaped it into a report would pass every check above."""
    menu = (await client.post("/api/design?format=menu", json={"variant": "chr2:71:A>C"})).json()
    candidate = menu["candidates"][0]
    assert "outcome_top" not in candidate, "this is the report, flattened"
    assert "guide" in candidate or "pegrna" in candidate, sorted(candidate)


def test_the_page_offers_it() -> None:
    """The audience the note was written at is the one that cannot run its remedy."""
    assert 'id="download-menu"' in _INDEX
    assert re.search(r'getElementById\("download-menu"\)', _APP_JS), "no handler"
    assert re.search(r'download\("menu"', _APP_JS), "the handler asks for another format"


def test_every_format_the_page_asks_for_is_one_the_api_serves() -> None:
    """Including the new one — a button naming a format the API rejects is a dead link."""
    from alleleforge.web.api.app import DesignFormat

    asked = set(re.findall(r'download\("(\w+)"', _APP_JS))
    assert "menu" in asked, asked
    unknown = sorted(asked - {f.value for f in DesignFormat})
    assert not unknown, unknown


def test_the_note_that_sends_readers_there_still_exists() -> None:
    """If the report stops truncating, this whole file is about nothing."""
    from alleleforge.report.builder import WITHHELD_ALLELES_NOTE

    assert "ranked menu" in WITHHELD_ALLELES_NOTE, WITHHELD_ALLELES_NOTE


@pytest.mark.anyio
async def test_an_unknown_format_is_still_refused(client: httpx.AsyncClient) -> None:
    """Adding one must not turn the enum into a free-text field."""
    response = await client.post("/api/design?format=nonsense", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 422, response.text
    assert "menu" in json.dumps(response.json()), "the refusal does not list the real formats"
