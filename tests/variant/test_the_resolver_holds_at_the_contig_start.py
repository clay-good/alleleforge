"""Resolver edges a constant-mutation sweep found unpinned.

* **The first base of a contig.** Left-alignment rolls an indel left through a repeat and
  then re-anchors it on the preceding base, which position 0 does not have. A deletion in a
  run of `A`s at the very start must roll to 0 and stay there unanchored; one at position 1
  must anchor on base 0. Every existing fixture sat mid-contig, so the `pos > 0` guards
  could become `>= 0` or `> 1` without a failure.
* **The coordinate in the off-by-one message.** The suggested `try …` input is run by
  `test_an_off_by_one_message_says_which_convention`, but the same message also states
  where the asserted ref really is, and that number was free to be wrong.
* **RefSeq chromosome 1.** `NC_000001` → `chr1` comes from a `range(1, 23)`; starting
  the range at 2 dropped chromosome 1, and only `NC_000002` was ever resolved.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.variant import Variant
from alleleforge.variant.resolver import _left_align, resolve


def _reference(tmp_path: Path, sequence: str) -> ReferenceGenome:
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(f">chr1\n{sequence}\n")
    return ReferenceGenome(fasta, build="hg38")


def test_a_deletion_in_a_leading_repeat_rolls_to_zero_unanchored(tmp_path: Path) -> None:
    reference = _reference(tmp_path, "AAACGTACGTACGTACGT")
    aligned = _left_align(Variant(chrom="chr1", pos=2, ref="A", alt=""), reference)
    assert (aligned.pos, aligned.ref, aligned.alt) == (0, "A", "")


def test_a_deletion_at_position_one_anchors_on_base_zero(tmp_path: Path) -> None:
    reference = _reference(tmp_path, "GCATGCATGCATGCAT")
    aligned = _left_align(Variant(chrom="chr1", pos=1, ref="C", alt=""), reference)
    assert (aligned.pos, aligned.ref, aligned.alt) == (0, "GC", "G")


def test_the_off_by_one_message_states_where_the_ref_really_is(tmp_path: Path) -> None:
    rng = random.Random(19)
    bases = "".join(rng.choice("ACGT") for _ in range(2_000))
    reference = _reference(tmp_path, bases)
    index = next(i for i in range(1000, 1500) if bases[i + 1] != bases[i])
    with pytest.raises(ValueError) as caught:
        resolve(f"chr1:{index + 1}:{bases[index + 1]}>A", reference=reference)
    # Input is 1-based index + 1; the asserted base is really at 1-based index + 2.
    assert f"is at chr1:{index + 2} in 1-based terms" in str(caught.value)


def test_refseq_chromosome_one_resolves(tmp_path: Path) -> None:
    bases = "ACGT" * 500
    reference = _reference(tmp_path, bases)
    resolved = resolve(f"NC_000001.11:g.6{bases[5]}>T", reference=reference)
    assert resolved.variant.chrom == "chr1"


def test_no_base_before_the_contig_is_offered_as_a_remedy(tmp_path: Path) -> None:
    from alleleforge.variant.resolver import _ref_matches_at

    reference = _reference(tmp_path, "GCATGCATGCATGCAT")
    variant = Variant(chrom="chr1", pos=0, ref="A", alt="T")
    # Position -1 does not exist, whatever the asserted ref is.
    assert _ref_matches_at(variant, reference, -1) is False
    # Position 0 does, and is checked like any other.
    assert _ref_matches_at(Variant(chrom="chr1", pos=1, ref="G", alt="T"), reference, 0)


def test_an_empty_ref_insertion_still_gets_a_one_base_core(tmp_path: Path) -> None:
    from alleleforge.variant.resolver import _working_interval

    variant = Variant(chrom="chr1", pos=0, ref="", alt="A")
    interval = _working_interval(variant, 10, None)
    assert (interval.start, interval.end) == (0, 11)
