"""The served page could not hand a user the flat table.

The UI's export buttons were *Download PDF* and *Download JSON*: a printable document and
a nested object. The one format a bench scientist opens in a spreadsheet — and the one a
pipeline filters — had to be produced from another shell, which for a browser user means
not at all.

Two properties are pinned here rather than the button label. Every format the page asks
the API for must be a format the API accepts, which is the drift that actually breaks a
download (the page requesting `?format=csv` fails at runtime and nowhere else). And the
flat table must be among them, since that is the gap this closed.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from alleleforge.web.api.app import DesignFormat

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_APP_JS = (_FRONTEND / "app.js").read_text(encoding="utf-8")
_INDEX = (_FRONTEND / "index.html").read_text(encoding="utf-8")


def _requested_formats() -> set[str]:
    """Return the `?format=` values the page asks for, literal and via `download(...)`."""
    literal = set(re.findall(r"/api/design\?format=([a-z]+)", _APP_JS))
    called = set(re.findall(r'\bdownload\(\s*"([a-z]+)"', _APP_JS))
    formats = literal | called
    assert formats, "no design formats found in app.js — this check would be vacuous"
    return formats


def test_every_format_the_page_asks_for_is_one_the_api_accepts() -> None:
    unknown = sorted(_requested_formats() - {member.value for member in DesignFormat})
    assert not unknown, (
        f"the page requests {unknown} from /api/design, which does not accept them — a "
        "download that fails only at runtime, in the browser."
    )


def test_the_page_offers_the_flat_table() -> None:
    assert "tsv" in _requested_formats()
    assert 'id="download-tsv"' in _INDEX
    assert "download-tsv" in _APP_JS, "the button exists and nothing is wired to it"


@pytest.mark.anyio
async def test_each_offered_format_actually_returns_something(client: httpx.AsyncClient) -> None:
    """The buttons are only as good as the endpoint behind them."""
    for fmt in sorted(_requested_formats()):
        response = await client.post(f"/api/design?format={fmt}", json={"variant": "chr2:71:A>C"})
        assert response.status_code == 200, (fmt, response.text[:200])
        assert response.content, fmt
