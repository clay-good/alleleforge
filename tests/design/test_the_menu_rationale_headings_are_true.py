"""A heading is a claim about the lines under it.

Found by running `aforge design` and reading the page. The rationale block read:

    Why the other chemistries declined:
    - base_cbe: Cytosine base editing installs a C->T / G->A transition ...
    - cas9_nuclease: An SpCas9 double-strand break repaired by error-prone NHEJ ...
    - base_abe: eligible but no actionable candidate enumerated — no PAM match ...
    - prime: 90 candidate(s)

Run outcomes and caveats were appended as bare `- ` bullets in the declined list's own
format, immediately under its heading. So a reader met "prime: 90 candidate(s)" as a
reason prime *declined*, on a page where prime produced all 90 candidates — and the
chemistry that actually declined for a runtime reason (base_abe, no PAM in range) was
mixed in with the two that were never eligible at all. The distinction matters: "not the
right chemistry for this edit" and "the right chemistry, no site here" send a reader
somewhere different.

The notes have their own heading now. This pins that the declined list contains only
chemistries that were not run.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome

MakeRef = Callable[[dict[str, str]], ReferenceGenome]


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(11)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr2\n" + "".join(rng.choice("ACGT") for _ in range(3_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _rationale(reference: ReferenceGenome) -> str:
    menu = design("chr2:1500:G>A", reference=reference, run_offtarget=False)
    assert menu.candidates, "no candidates — the heading under test would not appear"
    return menu.rationale


def _bullets_under(rationale: str, heading: str) -> list[str]:
    lines = rationale.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    out = []
    for line in lines[start + 1 :]:
        if not line.startswith("- "):
            break
        out.append(line[2:])
    return out


def test_the_declined_list_holds_only_chemistries_that_were_not_run(
    reference: ReferenceGenome,
) -> None:
    rationale = _rationale(reference)
    ran = rationale.split("Eligible and run: ")[1].split("\n")[0].rstrip(".").split(", ")
    declined = _bullets_under(rationale, "Why the other chemistries declined:")
    assert declined, "nothing declined — this check would be vacuous"
    for bullet in declined:
        chemistry = bullet.split(":")[0]
        assert chemistry not in ran, (
            f"{chemistry!r} ran, but is listed under the declined heading: {bullet!r}"
        )


def test_the_run_outcomes_have_their_own_heading(reference: ReferenceGenome) -> None:
    rationale = _rationale(reference)
    notes = _bullets_under(rationale, "Run notes:")
    assert any("candidate(s)" in note for note in notes), (
        "the per-chemistry outcome notes are not under their own heading"
    )
    assert rationale.index("Why the other chemistries declined:") < rationale.index("Run notes:")
