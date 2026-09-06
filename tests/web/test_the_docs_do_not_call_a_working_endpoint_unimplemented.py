"""The docs told readers an endpoint returns `501`. It returns `200` with data.

`docs/api/web.md`'s endpoint table said "`GET /api/bench` | CRISPR-Bench (`501` until Phase
14)". Phase 14 shipped: the endpoint lists all five tasks with their kind, chemistry,
dataset and metric battery. A reader following the documentation would not call it — a
capability made unreachable by prose rather than by code, which is the same outcome as not
having built it.

The guard reads the table and, for every row whose text claims a not-implemented status,
calls the endpoint and fails if it works. It is deliberately one-directional: documenting
something as available and having it 501 is a different bug, caught by the endpoint tests.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from alleleforge.web.api.app import create_app

_DOC = (Path(__file__).resolve().parents[2] / "docs" / "api" / "web.md").read_text(encoding="utf-8")


def _rows_claiming_unimplemented() -> list[tuple[str, str]]:
    rows = []
    for line in _DOC.splitlines():
        if not line.startswith("| `GET ") and not line.startswith("| `POST "):
            continue
        if "501" not in line:
            continue
        match = re.search(r"`(GET|POST) (/[^`]+)`", line)
        if match:
            rows.append((match.group(1), match.group(2)))
    return rows


def test_no_documented_501_actually_works() -> None:
    client = TestClient(create_app())
    for method, path in _rows_claiming_unimplemented():
        if "{" in path:  # a templated path needs an id we cannot invent
            continue
        response = client.request(method, path)
        assert response.status_code == 501, (
            f"docs/api/web.md calls {method} {path} unimplemented, and it returned "
            f"{response.status_code} — a capability made unreachable by prose"
        )


def test_the_bench_endpoint_is_documented_as_working() -> None:
    """The row this test was written for: it must not slip back."""
    assert "GET /api/bench" in _DOC
    body = TestClient(create_app()).get("/api/bench").json()
    assert body["tasks"], "the endpoint the docs now describe returns nothing"
    assert {"task", "kind", "chemistry", "dataset", "primary_metric"} <= set(body["tasks"][0])
