"""The cache key folds in two spans, and nothing checked that their ends distinguish it.

`search_signature`'s docstring says why `on_target` is in the key at all: *"otherwise a
bare scan and an on-target-excluding scan collide on one key and one is served the
other's report, silently either counting the self-match or hiding a perfect-score
site."* The same reasoning covers `regions`, the restriction a caller scans within.

An ordered-opposite sweep swapped each span's `start` for its `end` in turn — so the key
is built from `(end, end)` instead of `(start, end)` — and the whole suite stayed green
for all four. The key still *looks* like it carries the span, and still changes when the
span moves as a whole; what it stops doing is distinguishing two spans that share one
end. A guide whose on-target match was dropped at `chr1:100-120` and another at
`chr1:95-120` then hash alike, and the second is served the first's off-target report.

That is the one failure an off-target cache must not have, and it is invisible to every
test that only asks whether caching works: both searches return *a* report, promptly,
and the wrong one is indistinguishable from the right one without the coordinates.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.cache import search_signature
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import GenomicInterval, Strand

_SPACER = "ACGTACGTACGTACGTACGT"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    rng = random.Random(3)
    fasta = tmp_path / "ref.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(2_000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


def _span(start: int, end: int) -> GenomicInterval:
    return GenomicInterval(chrom="chr1", start=start, end=end, strand=Strand.PLUS)


def _signature(reference: ReferenceGenome, **over: object) -> str:
    kwargs: dict[str, object] = {
        "reference": reference,
        "mismatches": 3,
        "dna_bulges": 0,
        "rna_bulges": 0,
        "cfd_threshold": 0.2,
        "mit_threshold": 0.2,
        "regions": (),
        "on_target": None,
    }
    kwargs.update(over)
    return search_signature(_SPACER, PAM(pattern="NGG"), **kwargs)  # type: ignore[arg-type]


def test_the_same_inputs_give_the_same_key(reference: ReferenceGenome) -> None:
    """The premise: a key that changed every call would pass every check below."""
    assert _signature(reference, on_target=_span(100, 120)) == _signature(
        reference, on_target=_span(100, 120)
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ((100, 120), (95, 120)),  # same end, different start
        ((100, 120), (100, 125)),  # same start, different end
    ],
)
def test_two_on_targets_sharing_one_end_do_not_share_a_key(
    reference: ReferenceGenome, first: tuple[int, int], second: tuple[int, int]
) -> None:
    assert _signature(reference, on_target=_span(*first)) != _signature(
        reference, on_target=_span(*second)
    ), f"{first} and {second} hash alike"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ((200, 400), (150, 400)),
        ((200, 400), (200, 450)),
    ],
)
def test_two_restrictions_sharing_one_end_do_not_share_a_key(
    reference: ReferenceGenome, first: tuple[int, int], second: tuple[int, int]
) -> None:
    """`regions` is the window a caller restricted the scan to; a wider one is a different
    search, and a report for one must not be served for the other."""
    assert _signature(reference, regions=(_span(*first),)) != _signature(
        reference, regions=(_span(*second),)
    ), f"{first} and {second} hash alike"


def test_an_absent_on_target_is_its_own_key(reference: ReferenceGenome) -> None:
    """The case the docstring names: a bare scan is not an on-target-excluding scan."""
    assert _signature(reference, on_target=None) != _signature(reference, on_target=_span(100, 120))
