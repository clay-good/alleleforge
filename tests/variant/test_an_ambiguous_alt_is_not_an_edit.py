"""`chr1:15000:C>N` resolved, designed, and blamed the reference for an assembly gap.

The variant parser admits `ACGTN` in both alleles. In a **ref** that is right: a VCF
record at an assembly gap says `N`, and the reference-base check compares it against the
genome like any other allele. In an **alt** it is not a base anyone can write — no oligo
carries it, no editor installs it, no outcome distribution has it as a category.

So the request went through, and failed four layers down inside the pegRNA enumerator,
which reported:

    prime: eligible but no actionable candidate enumerated — … the RT template spans an
    assembly gap (N) (200) …

on a contig of pure ACGT. The `N` was in the user's own input, and the message sent them
to look for a gap in their FASTA. Every other IUPAC code is already refused by the parser
as an unrecognized variant; `N` in an alt is now refused too, where writing is what the
allele means, and the enumerator's gap message is true again.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.variant.resolver import resolve


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(23)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(4_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _ref_base(reference: ReferenceGenome, one_based: int) -> str:
    return "".join(Path(reference.path).read_text().split("\n")[1:])[one_based - 1]


def test_an_n_alt_is_refused_where_the_user_typed_it(reference: ReferenceGenome) -> None:
    base = _ref_base(reference, 2000)
    with pytest.raises(ValueError, match="not a base that can be written") as caught:
        resolve(f"chr1:2000:{base}>N", reference=reference)
    message = str(caught.value)
    assert "alt" in message, message
    # And it says where N *is* legitimate, so a VCF user is not left guessing.
    assert "ref" in message and "assembly gap" in message, message


def test_the_concrete_alt_still_resolves(reference: ReferenceGenome) -> None:
    """The floor: the refusal must not swallow ordinary variants."""
    base = _ref_base(reference, 2000)
    alt = "A" if base != "A" else "G"
    assert resolve(f"chr1:2000:{base}>{alt}", reference=reference) is not None


def test_an_n_ref_is_still_accepted() -> None:
    """A VCF record at an assembly gap is a real record, and this must not refuse it."""
    from alleleforge.types.variant import Variant

    assert Variant(chrom="chr1", pos=19, ref="N", alt="A").ref == "N"


def test_the_gap_reason_is_now_only_about_the_genome(reference: ReferenceGenome) -> None:
    """The enumerator's "spans an assembly gap" note may no longer be caused by input.

    Without the refusal above, `>N` reached the pegRNA enumerator and every candidate was
    skipped with that reason, on a reference with no gap in it.
    """
    base = _ref_base(reference, 2000)
    alt = "A" if base != "A" else "G"
    menu = design(
        resolve(f"chr1:2000:{base}>{alt}", reference=reference),
        reference=reference,
        intent=EditIntent.INSTALL,
        run_offtarget=False,
    )
    assert menu.candidates, "the fixture enumerates nothing; this check would be vacuous"
    assert "assembly gap" not in menu.rationale, menu.rationale
