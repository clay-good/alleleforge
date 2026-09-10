"""The HDR donor's re-cut logic, on the strand nothing measured it on.

Every donor and re-cut test in this repository uses a plus-strand fixture
(`PAD + SPACER + "TGG" + PAD`). Two neighbouring minus-strand geometries turned out to be
one base wrong — the nuclease cut site and the PE3 nicking guide's nick — for exactly that
reason: a plus-strand-only test on a two-strand rule.

This one is correct, and that is worth pinning rather than assuming. The properties are the
ones a bench scientist depends on:

* an edit inside the guide's seed needs no blocking mutation, because the repaired allele
  is no longer a substrate;
* a PAM-distal edit does need one, and gets it;
* and the mutation actually **destroys the PAM as read on the guide's own strand** — a
  plus-strand base changed so that its reverse complement is no longer `NGG`. Recording a
  mutation that does not block is worse than recording none, because `recut_blocked` is
  the field a reader trusts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.enumerate.cas9 import enumerate_cas9, hdr_donor
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import DNASequence
from alleleforge.variant.resolver import resolve

_START, _END = 100, 120
_PAM_AT = (97, 100)  # `CCA`: `TGG` read on the minus strand
_SPAN = f"chr1:{_START}-{_END}(-)"
_TRANSITION = {"A": "G", "G": "A", "C": "T", "T": "C"}


def _sequence() -> str:
    body = ["T"] * 300
    body[_START:_END] = list("ACGTACGTACGTACGTACGT")
    body[_PAM_AT[0] : _PAM_AT[1]] = list("CCA")
    return "".join(body)


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "minus.fa"
    fasta.write_text(">chr1\n" + _sequence() + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _donor(reference: ReferenceGenome, one_based: int) -> object:
    sequence = _sequence()
    base = sequence[one_based - 1]
    resolved = resolve(f"chr1:{one_based}:{base}>{_TRANSITION[base]}", reference=reference)
    guides = [
        g
        for g in enumerate_cas9(resolved, EditIntent.CORRECT, reference=reference)
        if str(g.placement) == _SPAN
    ]
    assert guides, f"no minus-strand guide for an edit at {one_based}"
    return hdr_donor(
        resolved, EditIntent.CORRECT, reference=reference, guide=guides[0], arm_length=20
    )


@pytest.mark.parametrize("one_based", [101, 105, 110])
def test_an_edit_in_the_seed_needs_no_blocking_mutation(
    one_based: int, reference: ReferenceGenome
) -> None:
    """The seed is the ten bases from the PAM-proximal end, which on this strand is the
    *low* genomic bound — measuring it from the other end mislabels every one of these."""
    donor = _donor(reference, one_based)
    assert donor.recut_blocked is True  # type: ignore[attr-defined]
    assert donor.blocking_mutation is None  # type: ignore[attr-defined]
    assert "disrupts the guide PAM or seed" in (donor.note or "")  # type: ignore[attr-defined]


@pytest.mark.parametrize("one_based", [111, 112, 113])
def test_a_pam_distal_edit_gets_one(one_based: int, reference: ReferenceGenome) -> None:
    donor = _donor(reference, one_based)
    assert donor.recut_blocked is True  # type: ignore[attr-defined]
    mutation = donor.blocking_mutation  # type: ignore[attr-defined]
    assert mutation is not None, "a PAM-distal correction leaves the guide's substrate intact"
    assert mutation.region == "pam"
    assert _PAM_AT[0] <= mutation.position < _PAM_AT[1]


def test_the_blocking_mutation_really_destroys_the_pam(reference: ReferenceGenome) -> None:
    """The effect, not the record. `recut_blocked` is the field a reader trusts, and a
    mutation that leaves an `NGG` in place would be worse than none."""
    donor = _donor(reference, 112)
    mutation = donor.blocking_mutation  # type: ignore[attr-defined]
    sequence = _sequence()
    assert sequence[mutation.position] == mutation.reference_base

    before = sequence[_PAM_AT[0] : _PAM_AT[1]]
    after = (
        before[: mutation.position - _PAM_AT[0]]
        + mutation.donor_base
        + before[mutation.position - _PAM_AT[0] + 1 :]
    )
    pam = PAM(pattern="NGG")
    # Read on the guide's own strand, which is what the enzyme sees.
    assert pam.matches(str(DNASequence(before).reverse_complement()))
    assert not pam.matches(str(DNASequence(after).reverse_complement()))
