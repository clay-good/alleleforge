"""Every `/api` endpoint must appear on the surfaces that claim to list them.

`docs/api/web.md` heads a table "Endpoints" and `README.md` carries the same table.
`POST /api/batch` — cohort design, a whole capability — was in the README's and absent
from the docs site's, so the page a user lands on from the documentation navigation
listed nine of the ten endpoints and gave no sign it was incomplete.

An undocumented endpoint is not a broken one, which is exactly why nothing caught it:
the route works, its tests pass, and the omission is only visible by comparing two
documents nobody diffs. This does the diff.

Sibling of `test_documented_env_vars_are_read`, run in the other direction: that one
asks whether every documented name is real, this one whether every real name is
documented. A public interface needs both, because the two failures are different —
a name that goes nowhere, and a capability nobody can find.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.web.api.app import create_app

_ROOT = Path(__file__).resolve().parents[2]
#: The two surfaces that present themselves as the list of endpoints.
_SURFACES = [_ROOT / "docs" / "api" / "web.md", _ROOT / "README.md"]


def _api_paths() -> list[str]:
    """Return every `/api` route path the app serves."""
    return sorted(
        {
            route.path
            for route in create_app().routes
            if getattr(route, "path", "").startswith("/api")
        }
    )


def _normalize(text: str) -> str:
    """Collapse a documented path so a renamed path parameter is not a failure.

    `GET /api/jobs/{id}` and the route's `/api/jobs/{job_id}` are the same endpoint;
    the parameter's name is an implementation detail the prose need not track.
    """
    out, depth = [], 0
    for ch in text:
        if ch == "{":
            depth += 1
            out.append("{}")
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def test_there_are_endpoints_to_check() -> None:
    """Guard the guard: an empty route list would pass vacuously."""
    paths = _api_paths()
    assert len(paths) >= 8, paths
    assert "/api/batch" in paths


@pytest.mark.parametrize("surface", _SURFACES, ids=lambda p: p.name)
def test_every_api_route_is_listed(surface: Path) -> None:
    text = _normalize(surface.read_text())
    missing = [p for p in _api_paths() if _normalize(p) not in text]
    assert not missing, (
        f"{surface.relative_to(_ROOT)} presents itself as the list of endpoints and "
        f"omits: {missing}. An endpoint nobody can find is an endpoint nobody has."
    )
