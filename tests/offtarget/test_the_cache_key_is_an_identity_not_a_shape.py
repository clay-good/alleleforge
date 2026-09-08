"""A warm cache reported a guide as spotless in a genome it cuts.

`reference_key` was `build` plus contig lengths. That is a *shape*, not an identity:
`build` is a label the caller picks (`--reference-fasta any.fa --reference hg38`), and
two FASTAs can share every contig name and length while differing in their bases — a
soft-masked copy, a patched build, a genome edited in place.

Measured with two 4 kb references of one shape, the second containing a perfect match for
the guide:

    second genome alone       2 sites, worst 1.000, specificity 0.333
    second genome, warm cache 0 sites, worst 0.000, specificity 1.000

An under-specified label fails to tell two records apart. An under-specified *key* serves
one run the other's answer — here the most reassuring output the system can produce, on
the opt-in flag whose whole promise is that it changes no result.

Hashing the bases is out of reach at genome scale, which is why the shape was chosen; the
file's identity on this machine stands in for them. The cost is that two byte-identical
copies at different paths no longer share entries, which is a rescan rather than a wrong
number — the direction a safety cache has to fail in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.cache import OffTargetCache, reference_key
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM

_SPACER = "GGAGGAATCCTCGACGGTAT"


def _reference(path: Path, seq: str) -> ReferenceGenome:
    path.write_text(f">chr1\n{seq}\n")
    return ReferenceGenome(path, build="hg38")


@pytest.fixture
def two_shapes(tmp_path: Path) -> tuple[ReferenceGenome, ReferenceGenome]:
    """Two references of identical build and contig length; one carries the guide."""
    import random

    random.seed(1)
    clean = "".join(random.choice("ACGT") for _ in range(4000))
    random.seed(2)
    bases = [random.choice("ACGT") for _ in range(4000)]
    bases[1000:1023] = list(_SPACER + "TGG")
    carrying = "".join(bases)
    assert len(clean) == len(carrying)
    return (
        _reference(tmp_path / "clean.fa", clean),
        _reference(tmp_path / "carrying.fa", carrying),
    )


def test_the_fixture_really_is_two_genomes_of_one_shape(
    two_shapes: tuple[ReferenceGenome, ReferenceGenome],
) -> None:
    """Without this the whole file could pass for the wrong reason."""
    clean, carrying = two_shapes
    assert clean.build == carrying.build
    assert clean.contig_length("chr1") == carrying.contig_length("chr1")
    assert clean.contigs == carrying.contigs
    assert search(_SPACER, PAM(pattern="NGG"), reference=clean).sites == ()
    assert search(_SPACER, PAM(pattern="NGG"), reference=carrying).sites


def test_a_cached_scan_of_one_genome_is_not_served_for_the_other(
    two_shapes: tuple[ReferenceGenome, ReferenceGenome], tmp_path: Path
) -> None:
    clean, carrying = two_shapes
    cache = OffTargetCache(root=tmp_path / "store")
    first = search(_SPACER, PAM(pattern="NGG"), reference=clean, cache=cache)
    second = search(_SPACER, PAM(pattern="NGG"), reference=carrying, cache=cache)
    assert first.sites == ()
    assert second.sites, "the warm cache served the other genome's report"
    assert second.specificity_score() < 0.5, second.specificity_score()


def test_the_same_genome_still_hits_the_cache(
    two_shapes: tuple[ReferenceGenome, ReferenceGenome], tmp_path: Path
) -> None:
    """The fix must not cost the feature: a repeat scan is still served."""
    _, carrying = two_shapes
    cache = OffTargetCache(root=tmp_path / "store")
    signature_first = reference_key(carrying)
    search(_SPACER, PAM(pattern="NGG"), reference=carrying, cache=cache)
    reopened = ReferenceGenome(carrying.path, build="hg38")
    assert reference_key(reopened) == signature_first
    again = search(_SPACER, PAM(pattern="NGG"), reference=reopened, cache=cache)
    assert again.sites


def test_a_genome_edited_in_place_is_a_different_key(tmp_path: Path) -> None:
    """The case a path-only identity would miss."""
    import os

    fasta = tmp_path / "g.fa"
    before = _reference(fasta, "ACGT" * 1000)
    key_before = reference_key(before)
    edited = "ACGT" * 999 + "TTTT"
    fasta.write_text(f">chr1\n{edited}\n")
    # Same path, same length; only the bytes and the mtime moved.
    os.utime(fasta, ns=(0, 1))
    after = ReferenceGenome(fasta, build="hg38")
    assert after.contig_length("chr1") == before.contig_length("chr1")
    assert reference_key(after) != key_before
