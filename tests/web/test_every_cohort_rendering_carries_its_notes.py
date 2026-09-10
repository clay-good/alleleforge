"""Four renderings of one cohort, and the JSON envelope had none of the notes.

The run-level notes — a population source built for another assembly, items with no
off-target search, a cross-chemistry sort comparing two uncalibrated models — have been in
the TSV and Parquet note block since those shipped, and the CLI prints them. `POST
/api/batch` returns a JSON envelope with `total`, `succeeded`, `failed`, `items`,
`provenance`, `coordinate_system` and `disclaimer`, and carried none of them — so an HTTP
client could discover a wrong-build population source only by scanning every row's
`offtarget_sources` mapping for a `:build-mismatch` key it has no reason to look for.

The envelope is the form an HTTP client actually consumes. It was the surface with the
least excuse and the least disclosure.

The guard's population is `BatchFormat` — the API's own enumeration of how a cohort can be
rendered — so a format added later is a failing test until it carries them too.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from alleleforge.design.cohort import design_many  # noqa: E402
from alleleforge.design.cohort_summary import (  # noqa: E402
    cohort_headline_notes,
    cohort_rows,
    cohort_to_tsv,
)
from alleleforge.genome.reference import ReferenceGenome  # noqa: E402
from alleleforge.web.api.app import BatchFormat  # noqa: E402

_ALT = {"A": "G", "G": "A", "C": "T", "T": "C"}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    random.seed(5)
    body = "".join(random.choice("ACGT") for _ in range(4000))
    body = body[:1000] + "ACCTGACTCCTGAGGAGAAG" + "TGG" + body[1023:]
    path = tmp_path / "ref.fa"
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


def _base(fasta: Path, one_based: int) -> str:
    import pyfaidx

    return str(pyfaidx.Fasta(str(fasta))["chr11"][one_based - 1 : one_based]).upper()


@pytest.fixture
def qualified(fasta: Path, tmp_path: Path) -> Any:
    """A run with something to qualify: a gnomAD file built for another assembly."""
    from alleleforge.data.gnomad import GnomadDB

    sites = tmp_path / "wrong.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\n"
        f"chr11\t1100\t{_ALT[_base(fasta, 1100)]}\t{_base(fasta, 1100)}\t0.02\t0.05\n"
    )
    variants = [f"chr11:{p}:{_base(fasta, p)}>{_ALT[_base(fasta, p)]}" for p in (1010, 1050)]
    return design_many(
        variants,
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(sites),
        populations=["afr"],
    )


def test_the_fixture_has_something_to_say(qualified: Any) -> None:
    """Without this the checks below pass on a run with no notes."""
    assert cohort_headline_notes(cohort_rows(qualified))


@pytest.mark.anyio
async def test_the_endpoint_carries_them(fasta: Path, tmp_path: Path) -> None:
    """Through the endpoint, not by constructing the envelope here.

    The first version of this built a `BatchResponse` itself and asserted the field
    serialized — which it does, being a field. Deleting the line in `_cohort_response`
    that fills it left that version green: it tested the model and not the wiring, which
    is the only part that had the defect.
    """
    import httpx

    from alleleforge.data.gnomad import GnomadDB
    from alleleforge.web.api.app import create_app

    sites = tmp_path / "wrong.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\n"
        f"chr11\t1100\t{_ALT[_base(fasta, 1100)]}\t{_base(fasta, 1100)}\t0.02\t0.05\n"
    )
    app = create_app(
        reference=ReferenceGenome(fasta, build="hg38"),
        gnomad=GnomadDB.from_sites_tsv(sites),
    )
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/batch",
            json={
                "variants": [f"chr11:1010:{_base(fasta, 1010)}>{_ALT[_base(fasta, 1010)]}"],
                "populations": ["afr"],
            },
        )
    assert response.status_code == 200, response.text
    notes = response.json()["notes"]
    assert any("build mismatch" in note for note in notes), notes


def test_every_format_the_api_offers_carries_them(qualified: Any) -> None:
    """Derived from `BatchFormat`: a format added later must carry them or fail here."""
    rows = cohort_rows(qualified)
    notes = cohort_headline_notes(rows)
    rendered: dict[str, str] = {}
    for fmt in BatchFormat:
        if fmt is BatchFormat.tsv:
            rendered[fmt.value] = cohort_to_tsv(rows, qualified.provenance)
        elif fmt is BatchFormat.json:
            rendered[fmt.value] = repr(notes)
        elif fmt is BatchFormat.parquet:
            # Only this branch needs the optional writer. Skipping the whole test where
            # it is absent would have taken the TSV and JSON checks with it — which is
            # how an install without one extra silently stops checking three surfaces.
            try:
                import pyarrow  # noqa: F401
            except ImportError:
                continue
            import tempfile

            from alleleforge.design.cohort_summary import cohort_to_parquet

            with tempfile.TemporaryDirectory() as tmp:
                path = cohort_to_parquet(rows, Path(tmp) / "c.parquet", qualified.provenance)
                rendered[fmt.value] = Path(path).read_bytes().decode("utf-8", "replace")
        else:  # pragma: no cover - a new format is the failure this exists for
            pytest.fail(f"{fmt.value} is a cohort rendering with no case here")
    for name, body in rendered.items():
        for note in notes:
            assert note in body, f"{name} does not carry {note!r}"


def test_the_page_renders_them_above_the_table() -> None:
    app_js = (
        Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "app.js"
    ).read_text(encoding="utf-8")
    assert "data.notes" in app_js, "the cohort tab does not render the run-level notes"
    index = app_js.index("data.notes")
    assert 'class="err"' in app_js[index : index + 150], "rendered as neutral text"
    # Above the table: a note under five hundred rows is a note nobody reaches.
    assert app_js.index("data.notes") < app_js.index("batchResults.innerHTML")
