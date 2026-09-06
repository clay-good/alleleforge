"""The cohort endpoint must not offer less than the single-design one.

Checking `design()`'s parameter list against each shell is the query that has found the
most in this project: a capability someone thought worth building and nobody finished
exposing. It had been run against the CLI. Run against the web API it turned up a gap
*inside* the API -- four options `DesignRequest` carries and `BatchRequest` did not,
all four of which `aforge batch` has had all along:

* `offtarget_regions` -- so the most expensive path was the one that could not be
  scoped, while the `--region` help calls scoping what usually makes a run practical;
* `allow_ng` / `allow_spry` -- a cohort is where a variant with no actionable NGG guide
  is *certain* to turn up, and the fallback built for exactly that case was unreachable,
  so the item came back empty with nothing the caller could do about it;
* `cell_context` -- no out-of-distribution flag was obtainable on the batch path.

The structural check is the point. Naming today's four fields would pass again the day a
fifth is added to one request model and not the other.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app
from alleleforge.web.api.models import BatchRequest, DesignRequest

#: Fields that are legitimately single-design only, each with the reason. A field may
#: only be here with one, so this cannot become a place to lose a capability.
_DESIGN_ONLY: dict[str, str] = {
    "variant": "the cohort takes `variants`, its plural",
    "render_candidates": "caps a rendered page; the cohort returns per-item summaries",
}


def test_the_cohort_request_offers_everything_the_single_design_one_does() -> None:
    # A floor first: "the cohort is missing nothing" is trivially true if the field
    # introspection returns nothing, which is the failure mode this whole file exists
    # to catch one level down.
    assert len(DesignRequest.model_fields) > 8, DesignRequest.model_fields
    assert len(BatchRequest.model_fields) > 5, BatchRequest.model_fields
    missing = sorted(
        set(DesignRequest.model_fields) - set(BatchRequest.model_fields) - set(_DESIGN_ONLY)
    )
    assert not missing, (
        f"options a single design accepts and a cohort cannot: {missing}. Wire them "
        "through, or record them in _DESIGN_ONLY with the reason a cohort cannot use them."
    )


def test_the_documented_exceptions_are_real_fields() -> None:
    """Guard the guard: an allowance must not outlive the field it excuses."""
    stale = sorted(set(_DESIGN_ONLY) - set(DesignRequest.model_fields))
    assert not stale, f"_DESIGN_ONLY names fields DesignRequest no longer has: {stale}"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("offtarget_regions", [{"chrom": "chr2", "start": 0, "end": 140, "strand": "+"}]),
        ("cell_context", "K562"),
        ("allow_ng", True),
        ("allow_spry", True),
    ],
)
async def test_the_cohort_endpoint_accepts_each_option(
    client: httpx.AsyncClient, field: str, value: object
) -> None:
    """Present in the schema is not the same as reaching the designer.

    A field can validate and be dropped on the floor by the handler -- the failure this
    project keeps finding -- so each one is sent through the live endpoint and the run
    has to succeed with it applied.
    """
    response = await client.post(
        "/api/batch", json={"variants": ["chr2:71:A>C"], "intent": "correct", field: value}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["failed"] == 0, body["items"]


async def test_scoping_the_cohort_search_actually_scopes_it(client: httpx.AsyncClient) -> None:
    """The strongest available check that the region reached the engine.

    A region naming a contig the reference does not have is refused by `search()`. If
    the field were accepted and discarded, this would succeed instead.
    """
    response = await client.post(
        "/api/batch",
        json={
            "variants": ["chr2:71:A>C"],
            "intent": "correct",
            "offtarget_regions": [{"chrom": "chrNope", "start": 0, "end": 10, "strand": "+"}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Per-item isolation means the item completes rather than erroring: every chemistry
    # declines, and the reason is what carries the refusal out. The item is "ok" with no
    # candidates, so the assertion has to read the reason, not the status.
    item = body["items"][0]
    reason = str(item["summary"]["no_candidate_reason"])
    assert "chrNope" in reason, f"the unknown contig was ignored: {item}"
    assert item["summary"]["n_candidates"] == 0


async def test_the_pam_fallback_actually_reaches_the_cohort_designer(tmp_path: Path) -> None:
    """`allow_ng` is the option a cohort needs most, and the hardest to fake.

    A cohort is where a variant with no actionable NGG guide is certain to turn up. This
    reference has no `GG` anywhere, so a knock-out yields nothing until the PAM-flexible
    fallback is offered. If the flag were accepted and discarded, both runs would be
    identical -- which is exactly the state the endpoint was in.
    """
    contig = "AATTAATTAATTAATTAATT" * 20
    fasta = tmp_path / "no_ngg.fa"
    fasta.write_text(">chr1\n" + contig + "\n")
    app = create_app(reference=ReferenceGenome(fasta, build="hg38"))
    body = {"variants": [f"chr1:101:{contig[100]}>C"], "intent": "knock_out"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        without = await c.post("/api/batch", json=body)
        with_ng = await c.post("/api/batch", json={**body, "allow_ng": True, "allow_spry": True})

    assert without.status_code == 200, without.text
    assert with_ng.status_code == 200, with_ng.text
    n_without = without.json()["items"][0]["summary"]["n_candidates"]
    n_with = with_ng.json()["items"][0]["summary"]["n_candidates"]
    assert n_without == 0, "the premise is wrong: NGG already yields a candidate here"
    assert n_with > 0, "allow_ng/allow_spry changed nothing; the flags never reached design()"


async def test_the_cell_context_actually_reaches_the_cohort_designer(
    client: httpx.AsyncClient,
) -> None:
    """A context outside any scorer's training distribution must flag the run OOD."""
    body = {"variants": ["chr2:71:A>C"], "intent": "correct"}

    plain = await client.post("/api/batch", json=body)
    odd = await client.post("/api/batch", json={**body, "cell_context": "not-a-real-cell-line"})
    assert plain.status_code == 200 and odd.status_code == 200

    assert plain.json()["items"][0]["summary"]["best_efficiency_in_distribution"] is True
    assert odd.json()["items"][0]["summary"]["best_efficiency_in_distribution"] is False, (
        "the cell context never reached design(); no OOD claim was made"
    )
