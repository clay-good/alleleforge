"""The per-patient table was the one product only the command line could make.

`aforge batch --summary-tsv` writes one row per cohort item, led by the research-use
disclaimer, the coordinate convention, the reference genome's identity and the seed. That
is the file a run over a patient VCF gets forwarded in, and `/api/batch` returned only
JSON — so an HTTP client had to rebuild the flattening and the note block to get the table
the CLI writes for free.

The flattening moved into the library in the round before this one, which is what makes
this a wiring fix rather than a second implementation: both shells call
`cohort_rows` / `cohort_to_tsv`, so the two cannot describe one run differently.

Parquet was deferred here once, and the enum said why: building it meant a writer *and*
the guard that its columns match the TSV's in order, this project having already shipped
two tables of the same numbers disagreeing about their columns. Both were built later —
the guard lives in `tests/design/test_the_cohort_table_has_two_encodings.py` — so the
cohort, which is the result that actually goes into a dataframe, now has both encodings
from both shells.
"""

from __future__ import annotations

import httpx
import pytest

from alleleforge.web.api.app import BatchFormat


async def _batch(client: httpx.AsyncClient, fmt: str) -> httpx.Response:
    response = await client.post(
        f"/api/batch?format={fmt}",
        json={"variants": ["chr2:71:A>C"], "run_offtarget": False, "max_per_chemistry": 2},
    )
    assert response.status_code == 200, response.text
    return response


@pytest.mark.anyio
async def test_the_cohort_tsv_is_served(client: httpx.AsyncClient) -> None:
    response = await _batch(client, "tsv")
    assert response.headers["content-type"].startswith("text/tab-separated-values")
    lines = response.text.splitlines()
    notes = [line for line in lines if line.startswith("#")]
    body = [line for line in lines if not line.startswith("#")]
    assert any("research tool" in note for note in notes), notes
    assert any("0-based" in note for note in notes), notes
    assert body[0].split("\t")[0] == "item_id"
    assert len(body) == 2, body


@pytest.mark.anyio
async def test_json_is_still_the_default(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/batch", json={"variants": ["chr2:71:A>C"], "run_offtarget": False}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["items"]


@pytest.mark.anyio
async def test_both_shells_render_the_same_table(client: httpx.AsyncClient, tmp_path) -> None:
    """One library function, so a cohort cannot be described two ways."""
    from typer.testing import CliRunner

    from alleleforge.cli.main import app as cli_app

    served = (await _batch(client, "tsv")).text
    served_header = next(line for line in served.splitlines() if not line.startswith("#"))

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    variants = tmp_path / "v.txt"
    variants.write_text("chr2:71:A>C\n")
    out = tmp_path / "summary.tsv"
    result = CliRunner().invoke(
        cli_app,
        [
            "batch",
            str(variants),
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--max-per-chemistry",
            "2",
            "--summary-tsv",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    cli_header = next(line for line in out.read_text().splitlines() if not line.startswith("#"))
    assert served_header == cli_header, (served_header, cli_header)


def test_the_cohort_offers_no_rendered_document() -> None:
    """A cohort has no single page; `aforge batch` has no `--format` for the same reason.

    `parquet` joined the flat table once `cohort_to_parquet` existed — the two encodings
    are one table, and a cohort is the result that actually goes into a dataframe. `html`
    and `pdf` still have nothing to render: a cohort produces per-item summaries, not one
    document.
    """
    values = {member.value for member in BatchFormat}
    assert values == {"json", "tsv", "parquet"}, values


@pytest.mark.anyio
async def test_an_unknown_format_is_refused_by_naming_the_real_ones(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/batch?format=pdf", json={"variants": ["chr2:71:A>C"], "run_offtarget": False}
    )
    assert response.status_code == 422
    for value in ("json", "tsv"):
        assert value in response.text, value


@pytest.mark.anyio
async def test_the_cohort_parquet_is_served(client: httpx.AsyncClient) -> None:
    """The encoding a pipeline reads, from the shell a pipeline speaks."""
    pytest.importorskip("polars")
    response = await _batch(client, "parquet")
    assert response.headers["content-type"] == "application/vnd.apache.parquet"
    assert response.content.startswith(b"PAR1"), response.content[:16]


@pytest.mark.anyio
async def test_both_shells_write_the_same_parquet_columns(
    client: httpx.AsyncClient, tmp_path
) -> None:
    """The same check as the TSV's, on the encoding whose columns nobody can eyeball."""
    pl = pytest.importorskip("polars")
    from typer.testing import CliRunner

    from alleleforge.cli.main import app as cli_app

    served = tmp_path / "served.parquet"
    served.write_bytes((await _batch(client, "parquet")).content)

    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    variants = tmp_path / "variants.txt"
    variants.write_text("chr2:71:A>C\n")
    out = tmp_path / "cli.parquet"
    result = CliRunner().invoke(
        cli_app,
        [
            "batch",
            str(variants),
            "--reference-fasta",
            str(fasta),
            "--no-offtarget",
            "--max-per-chemistry",
            "2",
            "--summary-parquet",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert pl.read_parquet(out).columns == pl.read_parquet(served).columns
