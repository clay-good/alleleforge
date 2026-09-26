"""The cut index handed to the outcome predictor, measured against a known number.

For a precise intent the target genome carries the alternate allele, so the context an
outcome predictor reads is overlaid with it. When that allele changes the sequence's
length everything 3' of it shifts, the cut included — and overlaying the sequence while
leaving the cut index alone yields the right sequence with the break in the wrong place:
a plausible-looking indel spectrum computed for a different locus, with nothing to flag it.

`test_cas9_indel_context.py` exists for exactly that failure and describes it in its own
docstring. Both of its decisive assertions are **tautologies**:

    offset = carried.index(context)
    assert context[cut] == carried[offset + cut]

`offset` is derived from `context`, so `carried[offset + cut]` *is* `context[cut]` for
every `cut` in range. The comparison holds whatever index the code recorded, and the
mutation the file was written to catch — dropping the shift, or applying it with the wrong
sign — survives it. The same is true of the sibling check that compares a ±5 window.

The repair is to compare against a number derived independently of the context. That
number is available: `_cut_outcome` takes its window as ``cut_site ± _OUTCOME_FLANK``, so
the *unshifted* cut index is exactly ``_OUTCOME_FLANK``, and a carried allele 5' of the cut
must move it by ``len(allele) - len(ref)`` and nothing else. Testing the arithmetic where
it happens also avoids asserting a cut convention this repository has had to correct three
times on the minus strand — the two guides the end-to-end fixture enumerates are both
minus-strand, and their cut indices sit on opposite sides of the naive expectation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.cas9 import _OUTCOME_FLANK, _cut_outcome
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import AlleleOutcome, EditOutcome
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand

#: The cut sits far enough into the contig that the window is never clipped at 0.
CUT_SITE = 200


class _RecordingPredictor:
    """Records exactly the ``(context, cut)`` it was asked to score."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def predict(self, context: str, cut: int, *, mark_frameshift: bool = False) -> EditOutcome:
        self.calls.append((context, cut))
        return EditOutcome(
            alleles=(AlleleOutcome(allele="wt", probability=1.0, is_intended=True),),
            partial=False,
        )

    def model_card(self) -> object:  # pragma: no cover - never reached
        raise NotImplementedError


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    # Distinct 10-base blocks, so a shifted window is visibly a different string.
    contig = "".join("ACGTTGCAAG"[i % 10] for i in range(500))
    fasta = tmp_path / "cut.fa"
    fasta.write_text(f">chr1\n{contig}\n")
    return ReferenceGenome(fasta, build="hg38")


def _guide() -> Guide:
    return Guide(
        spacer=Spacer(sequence=DNASequence("A" * 20)),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(
            chrom="chr1", start=CUT_SITE - 17, end=CUT_SITE + 3, strand=Strand.PLUS
        ),
        cut_site=CUT_SITE,
    )


def _recorded_cut(reference: ReferenceGenome, overlay: tuple[int, str, str] | None) -> int:
    predictor = _RecordingPredictor()
    _cut_outcome(_guide(), reference, predictor, False, overlay=overlay)  # type: ignore[arg-type]
    assert len(predictor.calls) == 1
    return predictor.calls[0][1]


def test_without_an_overlay_the_cut_sits_at_the_flank() -> None:
    """The premise every case below is measured against, stated rather than assumed."""
    assert _OUTCOME_FLANK == 20


def test_no_overlay_leaves_the_cut_at_the_window_centre(reference: ReferenceGenome) -> None:
    assert _recorded_cut(reference, None) == _OUTCOME_FLANK


@pytest.mark.parametrize(
    ("ref_base", "allele", "delta"),
    [
        ("ACGTAC", "A", -5),  # a deletion 5' of the cut pulls it back
        ("A", "ACGTAC", +5),  # an insertion 5' of the cut pushes it out
        ("AC", "GT", 0),  # a length-preserving substitution moves nothing
    ],
)
def test_an_allele_five_prime_of_the_cut_moves_it_by_the_length_change(
    reference: ReferenceGenome, ref_base: str, allele: str, delta: int
) -> None:
    """The shift is `len(allele) - len(ref)`, applied once, in that direction.

    Reversing the subtraction survives both of the existing file's checks; here it lands
    on the wrong side of `_OUTCOME_FLANK` and is named.
    """
    # Place the allele well inside the window and 5' of the cut.
    overlay = (CUT_SITE - 10, ref_base, allele)
    assert _recorded_cut(reference, overlay) == _OUTCOME_FLANK + delta


def test_an_allele_three_prime_of_the_cut_leaves_it_alone(reference: ReferenceGenome) -> None:
    """Only sequence 5' of the break moves the break."""
    overlay = (CUT_SITE + 5, "ACGTAC", "A")
    assert _recorded_cut(reference, overlay) == _OUTCOME_FLANK


def test_an_allele_ending_exactly_at_the_cut_still_moves_it(reference: ReferenceGenome) -> None:
    """The boundary of `rel + len(ref) <= cut_local`, which decides the shift.

    An allele whose last base is the one immediately 5' of the break is entirely
    upstream of it, so the break moves. Tightening the comparison to `<` leaves this
    one case unshifted — the cut lands one allele-length away from the base it names,
    on the input where the edit and the break are adjacent, which is the common case
    for a correction.
    """
    ref_base = "ACGTAC"
    overlay = (CUT_SITE - len(ref_base), ref_base, "A")
    assert _recorded_cut(reference, overlay) == _OUTCOME_FLANK - (len(ref_base) - 1)


def test_an_allele_at_the_very_start_of_the_window_is_applied(reference: ReferenceGenome) -> None:
    """The `0 <= rel` bound: an overlay at offset 0 of the window is inside it.

    Tightened to `0 < rel`, the carried allele is silently dropped and the predictor
    reads the *reference* base at the edited position — the patient's own allele
    missing from the sequence the outcome was computed on.
    """
    window_start = CUT_SITE - _OUTCOME_FLANK
    overlay = (window_start, "ACGTAC", "A")
    assert _recorded_cut(reference, overlay) == _OUTCOME_FLANK - 5

    predictor = _RecordingPredictor()
    _cut_outcome(_guide(), reference, predictor, False, overlay=overlay)  # type: ignore[arg-type]
    context = predictor.calls[0][0]
    assert context.startswith("A"), "the carried allele must open the window"
    assert len(context) == 2 * _OUTCOME_FLANK - 5


def _recorded(reference: ReferenceGenome, overlay: tuple[int, str, str] | None) -> tuple[str, int]:
    predictor = _RecordingPredictor()
    _cut_outcome(_guide(), reference, predictor, False, overlay=overlay)  # type: ignore[arg-type]
    assert len(predictor.calls) == 1
    return predictor.calls[0]


def test_an_allele_overrunning_the_window_end_is_not_applied(reference: ReferenceGenome) -> None:
    """The other bound, `rel + len(ref) <= len(context)`: a partial overlay is refused.

    An allele the window only partly covers cannot be spliced in without inventing the
    bases past the edge, so the overlay is skipped entirely.

    The context is asserted, not only the cut. A mis-written bound splices the allele in
    anyway and truncates the window — which leaves the cut index alone, so a check on the
    cut alone passes while the predictor reads a sequence that is two bases short and
    ends in an allele the genome does not have there.
    """
    untouched, _ = _recorded(reference, None)
    context, cut = _recorded(reference, (CUT_SITE + _OUTCOME_FLANK - 2, "ACGTAC", "A"))
    assert cut == _OUTCOME_FLANK
    assert context == untouched, "a refused overlay must leave the window exactly as fetched"


def test_an_allele_ending_exactly_at_the_window_end_is_applied(
    reference: ReferenceGenome,
) -> None:
    """The admitted extreme of the same bound: the allele's last base is the window's.

    Nothing has to be invented, so the overlay belongs. Tightened to `<`, this one case
    is dropped and the predictor reads the reference bases there instead of the
    patient's — and because it lies 3' of the break the cut does not move, so only the
    sequence betrays it.
    """
    untouched, _ = _recorded(reference, None)
    ref_base = "ACGTAC"
    rel = len(untouched) - len(ref_base)
    context, cut = _recorded(reference, (CUT_SITE - _OUTCOME_FLANK + rel, ref_base, "A"))

    assert cut == _OUTCOME_FLANK, "the allele is 3' of the break, so the break stays put"
    assert context != untouched, "the overlay must reach the sequence"
    assert context == untouched[:rel] + "A"
