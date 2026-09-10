"""The page told a user their genomic HGVS would be refused. It resolves.

The variant box's help read: "A ClinVar accession, dbSNP rsID or HGVS string needs a
lookup database this deployment has no way to supply, so those are refused". Two of the
three are right. The third is not: a **genomic** `g.` expression needs no lookup and no
projector — the resolver parses it directly — and `POST /api/resolve` answers
`chr1:g.500T>C` with the locus and `source: hgvs`.

`DesignRequest.variant`'s own description says "a **coding/protein** HGVS string", which
is exactly right, and the round that made the distinction reachable from the command line
(`--hgvs`) corrected the CLI's two copies of the sentence and the docs' copy. The page
kept the older, blunter wording, in the surface with no `--help` to correct it.

The sentence is a claim about what this API accepts, so this file makes it executable:
every form the page says works is posted and must be answered, and every form it says is
refused is posted and must be refused, with the message naming what to send instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.web.api.app import create_app

_INDEX = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend" / "index.html"
).read_text(encoding="utf-8")

#: What the page's help says the box takes. Each is a *form*, built below from the base
#: the served genome actually carries at the locus, so the check is about the form and
#: never about one fixture's sequence.
_ACCEPTED = ("coordinates", "a VCF record", "a genomic HGVS expression")

#: What it says needs a lookup this deployment cannot supply.
_REFUSED = {
    "a ClinVar accession": "VCV000000012",
    "a dbSNP rsID": "rs123456",
    "a coding HGVS string": "NM_000059.3:c.1234A>G",
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    import random

    random.seed(11)
    fasta = tmp_path / "g.fa"
    fasta.write_text(">chr1\n" + "".join(random.choice("ACGT") for _ in range(1200)) + "\n")
    return TestClient(create_app(reference=ReferenceGenome(fasta, build="hg38")))


def _alleles(client: TestClient) -> tuple[str, str]:
    """Return (ref, alt) at chr1:500 (1-based), read from the served genome."""
    from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

    ref = str(
        client.app.state.reference.fetch(  # type: ignore[attr-defined]
            GenomicInterval(
                chrom="chr1",
                start=499,
                end=500,
                strand=Strand.PLUS,
                coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
            )
        )
    )
    return ref, "A" if ref != "A" else "C"


def _form(label: str, ref: str, alt: str) -> str:
    return {
        "coordinates": f"chr1:500:{ref}>{alt}",
        "a VCF record": f"chr1\t500\t.\t{ref}\t{alt}",
        "a genomic HGVS expression": f"chr1:g.500{ref}>{alt}",
    }[label]


@pytest.mark.parametrize("label", _ACCEPTED)
def test_a_form_the_page_says_it_takes_is_answered(client: TestClient, label: str) -> None:
    variant = _form(label, *_alleles(client))
    response = client.post("/api/resolve", json={"variant": variant})
    assert response.status_code == 200, (label, variant, response.text)
    assert response.json()["variant"] == f"chr1:499:{_alleles(client)[0]}>{_alleles(client)[1]}"


@pytest.mark.parametrize("label", sorted(_REFUSED))
def test_a_form_the_page_says_it_refuses_is_refused_with_a_remedy(
    client: TestClient, label: str
) -> None:
    response = client.post("/api/resolve", json={"variant": _REFUSED[label]})
    assert response.status_code == 422, (label, response.text)
    detail = response.json()["detail"]
    assert "chrom:pos:ref>alt" in detail, (label, detail)


def test_the_help_text_distinguishes_the_two_kinds_of_hgvs() -> None:
    """The word that was missing, in the surface with no `--help` to correct it."""
    for phrase in ("genomic", "coding/protein"):
        assert phrase in _INDEX, phrase
    assert "or HGVS string needs a lookup" not in _INDEX, (
        "the page still says every HGVS form is refused; a genomic `g.` expression is not"
    )
