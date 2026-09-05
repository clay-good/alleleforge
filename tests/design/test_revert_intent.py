"""REVERT must stay mechanically identical to CORRECT, everywhere.

`REVERT` is exposed by the CLI (`--intent revert`) and reaches five independent
``intent in (CORRECT, REVERT)`` checks — routing, all three enumerators, and the HDR
donor. Nothing centralizes that; each site spells it out, and before this file none
of them had any REVERT coverage at all. A sixth branch added later that forgets
`REVERT` would silently fall through to the `INSTALL` behavior — writing the
*alternate* allele where the user asked for the reference, a wrong reagent from a
one-word omission.

These tests do not assert what REVERT does. They assert it does whatever CORRECT
does, which is the contract the code implements — and each one also asserts that
CORRECT and INSTALL genuinely *differ* at that locus, so the equivalence check
cannot pass vacuously on a locus where every intent returns nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from alleleforge.design.cas9 import design_cas9
from alleleforge.design.designer import design
from alleleforge.design.prime import design_prime
from alleleforge.design.routing import eligible_chemistries, route
from alleleforge.enumerate.base_editor import enumerate_base_edits
from alleleforge.enumerate.cas9 import carried_allele, enumerate_cas9, hdr_donor
from alleleforge.enumerate.prime import enumerate_prime
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.variant.resolver import ResolvedVariant, resolve

MakeRef = Callable[[str], ReferenceGenome]


def _contig() -> str:
    """A locus every chemistry reaches: AT-only but for two planted PAMs.

    The `TGG` gives a plus-strand pegRNA PAM whose nick and blunt cut both sit
    within reach of the edit at 70, and the `CCA` a minus-strand ngRNA PAM. All
    three enumerators produce candidates here, and CORRECT and INSTALL genuinely
    differ for each — which is what makes the equivalence assertions non-vacuous.
    """
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    return "".join(seq)


CONTIG = _contig()
POS = 70


@pytest.fixture
def make_reference(tmp_path: Path) -> MakeRef:
    counter = {"n": 0}

    def _make(contig: str) -> ReferenceGenome:
        counter["n"] += 1
        fasta = tmp_path / f"revert{counter['n']}.fa"
        fasta.write_text(f">chr2\n{contig}\n")
        return ReferenceGenome(fasta, build="hg38")

    return _make


def _resolve(reference: ReferenceGenome, contig: str, pos0: int) -> ResolvedVariant:
    return resolve(f"chr2:{pos0 + 1}:{contig[pos0]}>G", reference=reference)


def _base_edits(rv: ResolvedVariant, intent: EditIntent, *, reference: Any) -> Any:
    """Adapt the base-editor enumerator to the shared (rv, intent) call shape."""
    return enumerate_base_edits(rv, reference=reference, intent=intent)


def test_routing_treats_the_two_intents_alike(make_reference: MakeRef) -> None:
    ref = make_reference(CONTIG)
    rv = _resolve(ref, CONTIG, POS)
    assert eligible_chemistries(rv, EditIntent.REVERT) == eligible_chemistries(
        rv, EditIntent.CORRECT
    )
    assert eligible_chemistries(rv, EditIntent.REVERT) != eligible_chemistries(
        rv, EditIntent.INSTALL
    ), "CORRECT and INSTALL must differ here, or this proves nothing"
    assert [(d.chemistry, d.eligible) for d in route(rv, EditIntent.REVERT)] == [
        (d.chemistry, d.eligible) for d in route(rv, EditIntent.CORRECT)
    ]


def test_the_carried_allele_is_the_same(make_reference: MakeRef) -> None:
    """The decisive one: which allele the target genome is assumed to hold."""
    ref = make_reference(CONTIG)
    rv = _resolve(ref, CONTIG, POS)
    assert carried_allele(rv, EditIntent.REVERT) == carried_allele(rv, EditIntent.CORRECT)
    assert carried_allele(rv, EditIntent.REVERT) != carried_allele(rv, EditIntent.INSTALL)


@pytest.mark.parametrize(
    ("name", "enumerate_fn"),
    [("cas9", enumerate_cas9), ("base", _base_edits), ("prime", enumerate_prime)],
)
def test_every_enumerator_agrees(make_reference: MakeRef, name: str, enumerate_fn: Any) -> None:
    ref = make_reference(CONTIG)
    rv = _resolve(ref, CONTIG, POS)
    correct = enumerate_fn(rv, EditIntent.CORRECT, reference=ref)
    assert correct, f"{name}: locus produces nothing, so the comparison would be vacuous"
    assert enumerate_fn(rv, EditIntent.REVERT, reference=ref) == correct
    assert enumerate_fn(rv, EditIntent.INSTALL, reference=ref) != correct, (
        f"{name}: CORRECT and INSTALL must differ here, or this would pass even if "
        "REVERT fell through to INSTALL"
    )


def test_the_hdr_donor_is_the_same(make_reference: MakeRef) -> None:
    ref = make_reference(CONTIG)
    rv = _resolve(ref, CONTIG, POS)
    guide = enumerate_cas9(rv, EditIntent.CORRECT, reference=ref)[0]
    correct = hdr_donor(rv, EditIntent.CORRECT, reference=ref, guide=guide)
    revert = hdr_donor(rv, EditIntent.REVERT, reference=ref, guide=guide)
    install = hdr_donor(rv, EditIntent.INSTALL, reference=ref, guide=guide)
    assert correct is not None and revert is not None and install is not None
    assert str(revert.sequence) == str(correct.sequence)
    assert str(install.sequence) != str(correct.sequence)


def test_the_design_verticals_agree(make_reference: MakeRef) -> None:
    for vertical, name in ((design_cas9, "cas9"), (design_prime, "prime")):
        ref = make_reference(CONTIG)
        rv = _resolve(ref, CONTIG, POS)
        correct = vertical(rv, EditIntent.CORRECT, reference=ref, run_offtarget=False)
        revert = vertical(rv, EditIntent.REVERT, reference=ref, run_offtarget=False)
        assert correct, name
        assert len(revert) == len(correct), name
        # The reagents themselves, not just the count: a different carried allele
        # changes which protospacers are enumerated at all.
        assert [str(c.rationale) for c in revert] == [str(c.rationale) for c in correct]


def test_the_unified_entry_point_agrees(make_reference: MakeRef) -> None:
    ref = make_reference(CONTIG)
    rv = _resolve(ref, CONTIG, POS)
    correct = design(rv, reference=ref, intent=EditIntent.CORRECT, run_offtarget=False)
    revert = design(rv, reference=ref, intent=EditIntent.REVERT, run_offtarget=False)
    assert correct.candidates
    assert [c.chemistry for c in revert.candidates] == [c.chemistry for c in correct.candidates]
    assert [str(c.rationale) for c in revert.candidates] == [
        str(c.rationale) for c in correct.candidates
    ]
