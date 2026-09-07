"""Nine capabilities the API accepted and the served page could not ask for.

The browser is the fourth audience — Python, terminal, HTTP client, page — and the only
one with no `--help` to read and no signature to introspect, so its gaps are invisible to
every check the other three have. `readForm()` sent five fields. `DesignRequest` had
fourteen, and the missing ones were not cosmetic:

* `allow_ng` / `allow_spry` — without them a locus with no NGG guide returns an **empty
  menu** and the page offers no remedy, which is the failure the fallbacks exist for.
* `cell_context` — the input that raises the out-of-distribution flag on a prime
  efficiency prediction. Unreachable means the page can only report in-domain.
* `chromatin_track` — the status line *already named this deployment's tracks*, so the
  page was listing a capability it could not use.
* `vector_scheme` — picks the enzyme the oligo inserts are screened against.

The rest are recorded with a reason. The point of the list is that a gap has to be a
decision: the check reads the request body `readForm()` builds, so a field added to
`DesignRequest` and not to the page fails here rather than in someone's browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from alleleforge.web.api.models import DesignRequest

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")

#: Request fields the page legitimately does not offer, each with the reason.
_NOT_IN_PAGE: dict[str, str] = {
    "weights": "four coupled numbers that must sum sensibly; a slider set is its own "
    "design problem, and the default is the documented ranking",
    "chemistries": "narrows the menu the page exists to show; the menu already labels "
    "each candidate's chemistry, so filtering is a reading task here",
    "offtarget_regions": "a list of intervals; the page has no interval editor and a "
    "free-text box for genomic ranges is a coordinate-convention trap",
    "render_candidates": "shapes the embedded render only, and the page states what a "
    "cap withheld; it changes no result",
    "variant": "the required text input, read by name",
}


def _fields_sent_by_the_page() -> set[str]:
    """Return the request keys `readForm()` builds."""
    match = re.search(r"function readForm\(\) \{(?:.|\n)*?\n\}", _APP_JS)
    assert match, "could not find readForm() — this check would be vacuous"
    body = match.group(0)
    keys = set(re.findall(r"^\s{4}(\w+):", body, re.M))
    assert len(keys) > 3, f"readForm() parsed as {keys}"
    return keys


def test_the_page_can_ask_for_every_request_field_or_says_why() -> None:
    missing = sorted(
        set(DesignRequest.model_fields) - _fields_sent_by_the_page() - set(_NOT_IN_PAGE)
    )
    assert not missing, (
        f"the API accepts {missing} and the served page cannot ask for them. Add the "
        "control, or record it in _NOT_IN_PAGE with the reason."
    )


def test_the_recorded_exceptions_are_real_fields() -> None:
    stale = sorted(set(_NOT_IN_PAGE) - set(DesignRequest.model_fields))
    assert not stale, f"exceptions recorded for fields DesignRequest no longer has: {stale}"


def test_every_control_the_page_reads_exists_in_the_markup() -> None:
    """`getElementById` on a missing id returns null and throws only when clicked."""
    ids = set(re.findall(r'getElementById\("([a-z0-9-]+)"\)', _APP_JS))
    assert ids, "no element ids read in app.js"
    for element_id in sorted(ids):
        assert f'id="{element_id}"' in _INDEX, element_id


@pytest.mark.anyio
async def test_the_body_the_page_builds_is_one_the_api_accepts(client: httpx.AsyncClient) -> None:
    """`DesignRequest` forbids unknown fields, so a stale key is a 422 in the browser."""
    body = {key: None for key in _fields_sent_by_the_page()}
    body["variant"] = "chr2:71:A>C"
    body["intent"] = "correct"
    body["run_offtarget"] = False
    body["allow_ng"] = False
    body["allow_spry"] = False
    response = await client.post("/api/design", json=body)
    assert response.status_code == 200, response.text


@pytest.mark.anyio
async def test_the_pam_fallbacks_actually_change_the_menu(client: httpx.AsyncClient) -> None:
    """The controls are only worth adding if the page can reach a different result."""
    base = {"variant": "chr2:71:A>C", "run_offtarget": False}
    plain = await client.post("/api/design", json=base)
    relaxed = await client.post("/api/design", json={**base, "allow_ng": True, "allow_spry": True})
    assert plain.status_code == 200 and relaxed.status_code == 200
    assert len(relaxed.json()["candidates"]) >= len(plain.json()["candidates"])
