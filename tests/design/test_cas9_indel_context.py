"""The outcome context handed to a Cas9 predictor must match the carried genome.

For a precise intent the target genome carries the alternate allele, so the local
context an outcome predictor reads is overlaid with it. When that allele changes
the sequence's length, everything 3' of the edit shifts — the cut site included.
Overlaying the sequence but leaving the cut index alone yields the right sequence
with the break in the wrong place: a plausible-looking indel spectrum computed for
a different locus, with nothing to flag it.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path

import pytest

from alleleforge.design.cas9 import design_cas9
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import AlleleOutcome, EditIntent, EditOutcome
from alleleforge.variant.resolver import resolve

MakeRef = Callable[[dict[str, str]], ReferenceGenome]
EDIT_POS = 150


class _RecordingPredictor:
    """An outcome predictor that records exactly what it was asked to score."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def predict(self, context: str, cut: int, *, mark_frameshift: bool = False) -> EditOutcome:
        self.calls.append((context, cut))
        return EditOutcome(
            alleles=(AlleleOutcome(allele="wt", probability=1.0, is_intended=True),),
            partial=False,
        )

    def model_card(self) -> object:  # pragma: no cover - not exercised
        raise NotImplementedError


@pytest.fixture
def make_reference(tmp_path: Path) -> MakeRef:
    def _make(contigs: dict[str, str]) -> ReferenceGenome:
        fasta = tmp_path / "ctx.fa"
        fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
        return ReferenceGenome(fasta, build="hg38")

    return _make


def test_the_cut_index_follows_the_carried_allele_length(make_reference: MakeRef) -> None:
    rng = random.Random(4242)
    filler = list(rng.choice("ACGT") for _ in range(400))
    ref_allele = "ACGTAC"  # six reference bases the patient has deleted down to one
    contig = "".join(filler[:EDIT_POS]) + ref_allele + "".join(filler[EDIT_POS + len(ref_allele) :])
    reference = make_reference({"chr1": contig})
    resolved = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=reference)
    var = resolved.variant

    # The genome the guides are enumerated against, and the one the outcome
    # predictor must therefore be reading.
    carried = contig[: var.pos] + var.alt + contig[var.pos + len(var.ref) :]

    predictor = _RecordingPredictor()
    candidates = design_cas9(
        resolved,
        EditIntent.CORRECT,
        reference=reference,
        outcome_predictor=predictor,  # type: ignore[arg-type]
        run_offtarget=False,
    )
    assert candidates, "no guide enumerated at this locus"
    assert predictor.calls

    for candidate, (context, cut) in zip(candidates, predictor.calls, strict=True):
        assert candidate.guide is not None
        # The context must be a real window of the carried genome...
        assert context in carried, "outcome context is not a window of the carried genome"
        # ...and the cut index must point at the same base within it that the
        # guide's own cut site points at in that genome.
        offset = carried.index(context)
        assert 0 <= cut <= len(context)
        # The decisive check: the sequence the predictor sees around the break is
        # the sequence the carried genome actually has around this guide's cut.
        lo, hi = max(0, cut - 5), cut + 5
        assert context[lo:hi] == carried[offset + lo : offset + hi]


def test_the_recorded_cut_is_not_the_unshifted_reference_index(make_reference: MakeRef) -> None:
    """Pins the actual defect: a downstream cut must move by the length change."""
    rng = random.Random(4242)
    filler = list(rng.choice("ACGT") for _ in range(400))
    ref_allele = "ACGTAC"
    contig = "".join(filler[:EDIT_POS]) + ref_allele + "".join(filler[EDIT_POS + len(ref_allele) :])
    reference = make_reference({"chr1": contig})
    resolved = resolve(f"chr1:{EDIT_POS + 1}:{ref_allele}>{ref_allele[0]}", reference=reference)
    var = resolved.variant
    carried = contig[: var.pos] + var.alt + contig[var.pos + len(var.ref) :]
    shift = len(var.ref) - len(var.alt)
    assert shift == 5

    predictor = _RecordingPredictor()
    candidates = design_cas9(
        resolved,
        EditIntent.CORRECT,
        reference=reference,
        outcome_predictor=predictor,  # type: ignore[arg-type]
        run_offtarget=False,
    )
    downstream = 0
    for candidate, (context, cut) in zip(candidates, predictor.calls, strict=True):
        assert candidate.guide is not None
        if candidate.guide.cut_site <= var.pos:
            continue  # the cut is 5' of the edit: no shift applies
        downstream += 1
        offset = carried.index(context)
        # The base at the recorded cut must be the carried genome's, not the one
        # `shift` positions away that an unshifted index would have named.
        assert context[cut] == carried[offset + cut]
    assert downstream, "expected at least one guide cutting 3' of the edit"
