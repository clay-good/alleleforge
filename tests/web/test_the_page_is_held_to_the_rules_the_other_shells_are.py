"""Two promises the served page made that the CLI is already tested not to make.

The browser is the fourth audience — Python, terminal, HTTP client, page — and the only
one with no `--help` to read and no signature to introspect, so a rule enforced on the
other three can pass everywhere and still be broken where a human is looking.

Both of these were found by opening the page.

**The example it invites you to type.** An accession, an rsID or a `c.`/`p.` string is
refused *by this surface*. The ClinVar and dbSNP lookups are file-backed, and a
client-supplied path on a server is a file-read primitive, so over HTTP there is no
equivalent of the CLI's `--clinvar`/`--dbsnp`; `c.`/`p.` needs a projector from the `hgvs`
library, which nothing ships. There is a spec requirement about this, and a
test that the CLI's own argument help must carry the caveat rather than listing five
forms unqualified. The page's placeholder read
`chr2:71:A>C · VCV000012345 · rs1234 · NM_000518.5:c.20A>T` with the caption "ClinVar
accession, dbSNP rsID, HGVS, VCF record, or coordinates" — five forms, no caveat, in the
most-copied string on the page, three of them a guaranteed 422.

**The promise in the banner.** "All compute is local — no sequence data is transmitted
off this deployment" is the sentence a reader checks before pasting a patient variant.
Enabling consequence annotation makes it false. The API description was already fixed to
say what *this* deployment does; the banner, which is where a human reads it, still said
the other thing.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.variant.effect import VepRestPredictor
from alleleforge.web.api.app import create_app

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")

#: Input forms needing a lookup database or the `hgvs` library, which no shell supplies.
#: Kept in step with `tests/test_a_shell_example_uses_a_form_that_shell_can_resolve`.
_NEEDS_A_DATABASE = re.compile(r"\b(VCV\d+|rs\d+|[A-Z_0-9.]+:[cp]\.\S+)")


def _placeholders() -> list[str]:
    found = re.findall(r'placeholder="([^"]*)"', _INDEX)
    assert found, "no placeholders found in the page; this check would be vacuous"
    return found


def test_no_placeholder_offers_a_form_this_shell_refuses() -> None:
    offenders = [p for p in _placeholders() if _NEEDS_A_DATABASE.search(p)]
    assert not offenders, (
        f"the page invites a reader to type {offenders}, which it always refuses. A "
        "placeholder is the most-copied example on a surface with no --help."
    )


def test_the_input_captions_name_the_limit_rather_than_five_forms() -> None:
    """The rule the CLI's argument help is already held to, applied where humans read."""
    captions = re.findall(r"<small>((?:.|\n)*?)</small>", _INDEX)
    variant_captions = [c for c in captions if "chrom:pos" in c or "per line" in c]
    assert len(variant_captions) == 2, f"expected both variant captions, got {variant_captions}"
    for caption in variant_captions:
        assert "no way to supply" in caption or "cannot supply" in caption, (
            "the caption lists the input forms without saying which ones this "
            "deployment cannot resolve"
        )


@pytest.fixture
def vep_app(reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(
        VepRestPredictor, "predict", lambda self, variant, *, transcript="MANE_SELECT": None
    )
    return create_app(reference=reference, effect=VepRestPredictor(consent=True))


def test_the_transmission_promise_is_a_element_the_page_can_correct() -> None:
    """A hardcoded sentence cannot be true for both kinds of deployment."""
    assert 'id="transmission"' in _INDEX, (
        "the no-transmission promise is not addressable, so a deployment that does "
        "transmit cannot correct it"
    )
    assert "transmission" in _APP_JS, "nothing ever rewrites the promise"
    assert "vep_enabled" in _APP_JS


@pytest.mark.anyio
async def test_a_transmitting_deployment_reports_itself_to_the_page(
    vep_app: FastAPI,
) -> None:
    """The page rewrites from health, so health must say it — end to end, not by regex."""
    transport = httpx.ASGITransport(app=vep_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health = (await client.get("/api/health")).json()
    assert health["vep_enabled"] is True, (
        "the page decides what to say about transmission from this field"
    )
