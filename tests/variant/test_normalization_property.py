"""Property-based check that normalization/left-alignment preserves the edit.

The single most important correctness property of the variant pipeline: resolving a variant
must never change the biological edit the caller asked for. We verify it differentially —
the edited genome implied by the *resolved* (normalized, left-aligned) variant must be
byte-identical to the edited genome implied by the caller's *original* asserted variant,
computed by an independent splice-in oracle. This is strictly stronger than idempotence: a
normalization that silently relocated or altered an indel would pass idempotence but fail
here (cf. the R18 delins-corruption and R33 wrong-build-laundering fixes).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import resolve

# A repeat- and homopolymer-rich contig where left-alignment actually has work to do.
CHR1_SEQ = "TTTTTACGTACGTCAAAGTTGGCCAATTGGAAAAAAAA"


def _apply_edit(genome: str, pos: int, ref: str, alt: str) -> str:
    """Independent oracle: splice ``alt`` in for ``ref`` at 0-based ``pos``."""
    return genome[:pos] + alt + genome[pos + len(ref) :]


@pytest.fixture(scope="module")
def chr1_reference(tmp_path_factory: pytest.TempPathFactory) -> ReferenceGenome:
    fasta = tmp_path_factory.mktemp("norm") / "chr1.fa"
    fasta.write_text(f">chr1\n{CHR1_SEQ}\n")
    return ReferenceGenome(fasta, build="hg38")


@given(
    pos=st.integers(min_value=0, max_value=len(CHR1_SEQ) - 1),
    reflen=st.integers(min_value=0, max_value=5),
    alt=st.text(alphabet="ACGT", min_size=0, max_size=5),
)
@settings(max_examples=400, deadline=None)
def test_normalization_preserves_the_edit(
    chr1_reference: ReferenceGenome, pos: int, reflen: int, alt: str
) -> None:
    seq = CHR1_SEQ
    if pos + reflen > len(seq):
        return
    ref = seq[pos : pos + reflen]
    if ref == alt:
        return  # a no-op edit is not interesting

    try:
        resolved = resolve(
            Variant(chrom="chr1", pos=pos, ref=ref, alt=alt), reference=chr1_reference
        )
    except ValueError:
        return  # e.g. an anchorless insertion — resolve's documented domain, not a bug

    nv = resolved.variant
    # The normalized ref must genuinely sit on the reference (no phantom span)...
    assert seq[nv.pos : nv.pos + len(nv.ref)] == nv.ref
    # ...and applying it must reproduce exactly the caller's requested edit.
    assert _apply_edit(seq, nv.pos, nv.ref, nv.alt) == _apply_edit(seq, pos, ref, alt)
