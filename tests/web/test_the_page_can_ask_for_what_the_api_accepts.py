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

from alleleforge.web.api.models import BatchRequest, DesignRequest

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


def _fields_sent_by(builder: str) -> set[str]:
    """Return the request keys the named `read*Form()` function builds."""
    match = re.search(rf"function {builder}\(\) \{{(?:.|\n)*?\n\}}", _APP_JS)
    assert match, f"could not find {builder}() — this check would be vacuous"
    keys = set(re.findall(r"^\s{4}(\w+):", match.group(0), re.M))
    assert len(keys) > 3, f"{builder}() parsed as {keys}"
    return keys


def _fields_sent_by_the_page() -> set[str]:
    return _fields_sent_by("readForm")


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


#: Controls the single-variant panel has that the cohort panel legitimately lacks, with
#: the reason — the same shape `_DESIGN_ONLY` has for the request models.
_SINGLE_VARIANT_ONLY: dict[str, str] = {
    "vector_scheme": "picks the enzyme the report's oligo screen uses; the cohort "
    "endpoint returns per-item summaries and builds no oligos, so nothing is screened",
}

#: `BatchRequest` fields the cohort panel legitimately does not offer. It inherits the
#: single-variant panel's reasons, minus that panel's own input field.
_NOT_IN_BATCH_PANEL: dict[str, str] = {
    key: reason for key, reason in _NOT_IN_PAGE.items() if key in BatchRequest.model_fields
} | {"variants": "the required textarea"}


def test_the_cohort_panel_offers_what_the_single_variant_one_does() -> None:
    """The project's cohort-parity requirement, applied to the surface it was missing.

    `aforge batch` and `BatchRequest` are each guarded against falling behind their
    single-variant sibling. The served page was not, and it fell behind in the round that
    added the options: a cohort is where a PAM fallback matters most, because a variant
    with no NGG guide is the row that comes back empty.
    """
    single = _fields_sent_by("readForm") - {"variant"}
    batch = _fields_sent_by("readBatchForm") - {"variants"}
    missing = sorted(single - batch - set(_SINGLE_VARIANT_ONLY))
    assert not missing, (
        f"the single-variant panel sends {missing} and the cohort panel does not; a "
        "cohort is where these matter most."
    )


def test_the_cohort_panel_can_ask_for_every_batch_field_or_says_why() -> None:
    missing = sorted(
        set(BatchRequest.model_fields) - _fields_sent_by("readBatchForm") - set(_NOT_IN_BATCH_PANEL)
    )
    assert not missing, (
        f"/api/batch accepts {missing} and the cohort panel cannot ask for them. Add the "
        "control, or record it in _NOT_IN_BATCH_PANEL with the reason."
    )


def test_the_batch_allowances_are_real_fields() -> None:
    stale = sorted(set(_NOT_IN_BATCH_PANEL) - set(BatchRequest.model_fields))
    assert not stale, f"exceptions recorded for fields BatchRequest no longer has: {stale}"


def test_the_single_variant_only_allowances_are_really_single_variant_only() -> None:
    """An allowance must not excuse a field the cohort endpoint would happily accept."""
    wrong = sorted(set(_SINGLE_VARIANT_ONLY) & set(BatchRequest.model_fields))
    assert not wrong, f"/api/batch accepts these, so the cohort panel should offer them: {wrong}"
    absent = sorted(set(_SINGLE_VARIANT_ONLY) - set(DesignRequest.model_fields))
    assert not absent, f"allowances for controls the single-variant panel lacks too: {absent}"


@pytest.mark.anyio
async def test_the_cohort_body_the_page_builds_is_one_the_api_accepts(
    client: httpx.AsyncClient,
) -> None:
    body = {key: None for key in _fields_sent_by("readBatchForm")}
    body["variants"] = ["chr2:71:A>C"]
    body["intent"] = "correct"
    body["run_offtarget"] = False
    body["allow_ng"] = False
    body["allow_spry"] = False
    response = await client.post("/api/batch", json=body)
    assert response.status_code == 200, response.text
