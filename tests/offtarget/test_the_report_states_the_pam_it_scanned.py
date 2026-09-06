"""When the scan broadens the PAM, the report must say so.

`search()` broadens SpCas9's `NGG` to `NRG` before scanning, so a low-stringency `NAG`
off-target — which SpCas9 does cut, at reduced efficiency — is found rather than
missed. That is right, it is in `openspec/specs/offtarget-nomination/spec.md`, and the
code says why on the line that does it.

No surface said it. A scan over a CAG repeat reports:

    spacer CAGCAGCAGCAGCAGCAGCA / PAM NGG: 25 site(s), … specificity 0.130
      search: over 6,630 bases; up to 4 mismatches, 1 DNA / 1 RNA bulges; sites
      reported at CFD >= 0.2 or MIT >= 0.1; only 92% of the 6,630 …
      chr7:3537-3558(+)  pam=CAG  mm=2  score=0.2593  reference

`PAM NGG` in the header, `pam=CAG` on twenty-four of the rows, and nothing anywhere
reconciling them. The search description already enumerates every other condition the
numbers depend on — bases searched, mismatch and bulge budgets, both reporting
cut-offs, the MAF floor, the searchable fraction — and omitted this one.

It is load-bearing here: 24 of the 25 sites carry a `NAG` PAM, so the specificity of
0.130 is almost entirely produced by low-stringency PAMs. A reader who takes them for
`NGG` sites over-weights them; a reader who takes them for a bug under-weights them.
Both readings were available and neither was the truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

#: A CAG repeat contains no `GG`, so every site found in it has a low-stringency PAM.
_REPEAT_SPACER = "CAGCAGCAGCAGCAGCAGCA"


@pytest.fixture
def repeat_reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "repeat.fa"
    fasta.write_text(">chr7\n" + "A" * 40 + "CAG" * 30 + "T" * 40 + "\n")
    return ReferenceGenome(fasta)


def test_the_premise_holds(repeat_reference: ReferenceGenome) -> None:
    """Sites are found, and not one of them has the PAM the caller asked for."""
    report = search(_REPEAT_SPACER, PAM(pattern="NGG"), reference=repeat_reference)
    assert report.sites, "fixture found nothing — every check below would be vacuous"
    requested = PAM(pattern="NGG")
    assert not any(requested.matches(site.pam_sequence) for site in report.sites)


def test_the_description_names_the_scanned_pam(repeat_reference: ReferenceGenome) -> None:
    report = search(_REPEAT_SPACER, PAM(pattern="NGG"), reference=repeat_reference)
    description = report.search_description()
    assert "NRG" in description
    assert "NGG" in description
    assert "NAG" in description.upper() or "low-stringency" in description


def test_an_unbroadened_pam_says_nothing_extra(repeat_reference: ReferenceGenome) -> None:
    """A note that always appears is not a note; it must mark a real difference."""
    report = search(_REPEAT_SPACER, PAM(pattern="TTTV"), reference=repeat_reference)
    assert "NRG" not in report.search_description()
    assert "broadened" not in report.search_description()


def test_the_reported_sites_still_carry_their_own_pam(
    repeat_reference: ReferenceGenome,
) -> None:
    """The per-site PAM is what distinguishes a real NGG hit from a weak NAG one.

    Saying it once in the description does not replace saying it per row — an NGG and
    an NAG site at the same score carry very different risk.
    """
    report = search(_REPEAT_SPACER, PAM(pattern="NGG"), reference=repeat_reference)
    assert all(site.pam_sequence for site in report.sites)
