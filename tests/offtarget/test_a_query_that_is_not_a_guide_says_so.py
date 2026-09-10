"""`aforge offtarget ACGT` answered with 151,093 sites and specificity 0.000.

Every number an off-target report carries is about a *guide*. Handed a four-base query —
a typo, a truncated paste, a seed someone wanted to screen — the engine did exactly what
it is built to do and produced a report that is arithmetically correct and biologically
meaningless: a 4-mer occurs everywhere, so it "has" a hundred and fifty thousand
off-targets and a specificity of zero. Nothing on the page said the query was not a guide.

Labelled, not refused. Screening a seed sequence is a legitimate thing to do, and a tool
that refuses it has taken a decision away from a user who may know exactly what they are
asking. What is not legitimate is a specificity presented as if it described a reagent.

The range is published guide lengths: 20 nt for every chemistry this tool designs, 17-18
for the truncated SpCas9 guides of Fu et al. 2014, and 20-24 for Cas12a.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import GUIDE_SPACER_RANGE, PAM


@pytest.fixture(scope="module")
def reference(tmp_path_factory: pytest.TempPathFactory) -> ReferenceGenome:
    rng = random.Random(29)
    sequence = "".join(rng.choices("ACGT", k=40_000))
    path: Path = tmp_path_factory.mktemp("query") / "g.fa"
    path.write_text(">chr1\n" + sequence + "\n")
    return ReferenceGenome(path, build="hg38")


def _spacer(reference: ReferenceGenome, length: int) -> str:
    from alleleforge.types.sequence import CoordinateSystem, GenomicInterval, Strand

    return str(
        reference.fetch(
            GenomicInterval(
                chrom="chr1",
                start=1000,
                end=1000 + length,
                strand=Strand.PLUS,
                coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
            )
        )
    )


@pytest.mark.parametrize("length", [4, 10, GUIDE_SPACER_RANGE[0] - 1, GUIDE_SPACER_RANGE[1] + 1])
def test_a_query_outside_guide_length_is_labelled(reference: ReferenceGenome, length: int) -> None:
    report = search(_spacer(reference, length), PAM(pattern="NGG"), reference=reference)
    description = report.search_description()
    assert f"the query is {length} nt" in description, description
    assert "not a guide's off-target profile" in description
    # And the run still happens: this labels, it does not refuse.
    assert report.searched_bases > 0


@pytest.mark.parametrize("length", [GUIDE_SPACER_RANGE[0], 20, GUIDE_SPACER_RANGE[1]])
def test_a_guide_length_query_is_not_labelled(reference: ReferenceGenome, length: int) -> None:
    """The floor: the note must not appear on ordinary guides, or it is noise."""
    report = search(_spacer(reference, length), PAM(pattern="NGG"), reference=reference)
    assert "not a guide's off-target profile" not in report.search_description()


def test_the_label_reaches_the_shells(reference: ReferenceGenome) -> None:
    """It rides on the search description, so every surface that prints one carries it."""
    from typer.testing import CliRunner

    from alleleforge.cli.main import app

    result = CliRunner().invoke(
        app,
        ["offtarget", _spacer(reference, 6), "--reference-fasta", str(reference.path)],
    )
    assert result.exit_code == 0, result.output + result.stderr
    assert "not a guide's off-target profile" in result.stdout

    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    with TestClient(create_app(reference=reference)) as client:
        body = client.post("/api/offtarget", json={"spacer": _spacer(reference, 6)}).json()
    assert "not a guide's off-target profile" in body["search_description"]
