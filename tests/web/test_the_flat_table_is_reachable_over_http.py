"""The surface a pipeline reads must be obtainable from the HTTP shell too.

Two rounds went into making the flat per-candidate table trustworthy — the `#` note
block on the TSV, then the same notes in Parquet's file-level metadata — on the argument
that a machine-readable table is what a *pipeline* acts on, and a pipeline sees only the
columns it selected. Neither table could be obtained over HTTP: `?format=` offered
`json`, `html` and `pdf`, so the one audience that cannot open an HTML page was the one
the web shell had nothing for. Parquet could not be produced by any shell at all.

The formats are now the set `aforge design --format` offers, and the notes survive the
trip — a table delivered without its disclaimer, reference build and coordinate
convention is the state those two rounds existed to end.
"""

from __future__ import annotations

import io

import httpx
import pytest

from alleleforge.report.export import TSV_COLUMNS


async def _design(client: httpx.AsyncClient, fmt: str) -> httpx.Response:
    response = await client.post(f"/api/design?format={fmt}", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 200, response.text
    return response


@pytest.mark.anyio
async def test_the_tsv_arrives_with_its_note_block(client: httpx.AsyncClient) -> None:
    response = await _design(client, "tsv")
    assert response.headers["content-type"].startswith("text/tab-separated-values")
    lines = response.text.splitlines()
    notes = [line for line in lines if line.startswith("#")]
    assert any("research tool" in n for n in notes), notes
    assert any("hg38" in n for n in notes), notes
    assert any("0-based" in n for n in notes), notes
    header = next(line for line in lines if not line.startswith("#"))
    assert header.split("\t") == list(TSV_COLUMNS)


@pytest.mark.anyio
async def test_the_parquet_arrives_with_the_same_notes(client: httpx.AsyncClient) -> None:
    pl = pytest.importorskip("polars")
    response = await _design(client, "parquet")
    assert response.headers["content-type"] == "application/vnd.apache.parquet"
    body = response.content
    assert body[:4] == b"PAR1", "not a Parquet file"
    frame = pl.read_parquet(io.BytesIO(body))
    assert frame.columns == list(TSV_COLUMNS)
    metadata = pl.read_parquet_metadata(io.BytesIO(body))
    assert "research tool" in metadata["disclaimer"]
    notes = " ".join(v for k, v in metadata.items() if k.startswith("provenance_"))
    assert "hg38" in notes and "0-based" in notes


@pytest.mark.anyio
async def test_the_two_tables_hold_the_same_rows(client: httpx.AsyncClient) -> None:
    """One design, two encodings — a client must not have to choose which to trust."""
    pl = pytest.importorskip("polars")
    tsv = (await _design(client, "tsv")).text
    rows = [line for line in tsv.splitlines() if not line.startswith("#")][1:]
    frame = pl.read_parquet(io.BytesIO((await _design(client, "parquet")).content))
    assert frame.height == len(rows)


@pytest.mark.anyio
async def test_an_unknown_format_is_refused_by_naming_the_real_ones(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/design?format=csv", json={"variant": "chr2:71:A>C"})
    assert response.status_code == 422
    for fmt in ("json", "html", "pdf", "tsv", "parquet"):
        assert fmt in response.text, fmt
