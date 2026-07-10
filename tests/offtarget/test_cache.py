"""Tests for the cross-run reference off-target report cache (R4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.data.gnomad import GnomadDB, PopulationFrequency
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.cache import OffTargetCache, search_signature
from alleleforge.offtarget.engine import search
from alleleforge.offtarget.scoring import CfdScorer
from alleleforge.types.guide import PAM

from .conftest import PAD, SPACER

NGG = PAM(pattern="NGG")


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    fasta = tmp_path / "ref.fa"
    fasta.write_text(f">chr2\n{PAD}{SPACER}TGG{PAD}\n")
    return ReferenceGenome(fasta, build="hg38")


def test_signature_is_stable_and_input_sensitive(reference: ReferenceGenome) -> None:
    common = dict(
        reference=reference,
        mismatches=4,
        dna_bulges=1,
        rna_bulges=1,
        cfd_threshold=0.2,
        mit_threshold=0.1,
        regions=[],
    )
    base = search_signature(SPACER, NGG, **common)  # type: ignore[arg-type]
    assert base == search_signature(SPACER, NGG, **common)  # type: ignore[arg-type]
    assert base != search_signature(SPACER, NGG, **{**common, "mismatches": 2})  # type: ignore[arg-type]
    assert base != search_signature(SPACER, PAM(pattern="NRG"), **common)  # type: ignore[arg-type]


def test_cache_hit_returns_identical_report(reference: ReferenceGenome, tmp_path: Path) -> None:
    cache = OffTargetCache(root=tmp_path)
    first = search(SPACER, NGG, reference=reference, cache=cache)
    assert len(cache) == 1
    second = search(SPACER, NGG, reference=reference, cache=cache)
    assert second.model_dump_json() == first.model_dump_json()
    assert len(cache) == 1  # served from cache, nothing new stored


def test_changed_query_is_a_cache_miss(reference: ReferenceGenome, tmp_path: Path) -> None:
    cache = OffTargetCache(root=tmp_path)
    search(SPACER, NGG, reference=reference, cache=cache)
    search(SPACER, NGG, reference=reference, mismatches=2, cache=cache)
    assert len(cache) == 2  # a different budget keys a different entry


def test_cache_survives_across_runs(reference: ReferenceGenome, tmp_path: Path) -> None:
    # A second OffTargetCache over the same root is a fresh "run": the entry the
    # first run wrote is read back by the second without recomputing/storing.
    report = search(SPACER, NGG, reference=reference, cache=OffTargetCache(root=tmp_path))
    next_run = OffTargetCache(root=tmp_path)
    assert len(next_run) == 1  # the prior run's entry is on disk
    again = search(SPACER, NGG, reference=reference, cache=next_run)
    assert again.model_dump_json() == report.model_dump_json()
    assert len(next_run) == 1  # a hit — nothing new stored


def test_population_search_is_never_cached(reference: ReferenceGenome, tmp_path: Path) -> None:
    # gnomAD augmentation depends on external data the key can't capture: no cache.
    cache = OffTargetCache(root=tmp_path)
    gnomad = GnomadDB([PopulationFrequency(chrom="chr2", pos=8, ref="T", alt="G", overall_af=0.05)])
    search(SPACER, NGG, reference=reference, gnomad=gnomad, cache=cache)
    assert len(cache) == 0


def test_custom_scorer_is_never_cached(reference: ReferenceGenome, tmp_path: Path) -> None:
    # A custom scorer changes scores the signature does not see: no cache.
    cache = OffTargetCache(root=tmp_path)
    search(SPACER, NGG, reference=reference, scorer=CfdScorer(), cache=cache)
    assert len(cache) == 0


def test_on_target_is_part_of_the_signature(reference: ReferenceGenome) -> None:
    # `on_target` drops the guide's own self-match from the report, so it changes
    # the result and MUST key a distinct entry — otherwise a bare scan and an
    # on-target-excluding scan collide (regression for the R24 cache-key gap).
    from alleleforge.types.sequence import GenomicInterval, Strand

    common = dict(
        reference=reference,
        mismatches=4,
        dna_bulges=1,
        rna_bulges=1,
        cfd_threshold=0.2,
        mit_threshold=0.1,
        regions=[],
    )
    on_target = GenomicInterval(chrom="chr2", start=len(PAD), end=len(PAD) + 20, strand=Strand.PLUS)
    bare = search_signature(SPACER, NGG, **common)  # type: ignore[arg-type]
    excluded = search_signature(SPACER, NGG, on_target=on_target, **common)  # type: ignore[arg-type]
    assert bare != excluded
    # Naming-aware and stable: a bare-contig spelling keys the same entry.
    on_target_bare = on_target.model_copy(update={"chrom": "2"})
    assert excluded == search_signature(SPACER, NGG, on_target=on_target_bare, **common)  # type: ignore[arg-type]


def test_on_target_change_is_a_cache_miss(reference: ReferenceGenome, tmp_path: Path) -> None:
    # End-to-end: a bare scan and a scan that excludes the on-target self-match must
    # not share a cached report. Before the fix the second call was served the first
    # call's report — silently either counting the self-match or hiding a perfect site.
    from alleleforge.types.sequence import GenomicInterval, Strand

    cache = OffTargetCache(root=tmp_path)
    on_target = GenomicInterval(chrom="chr2", start=len(PAD), end=len(PAD) + 20, strand=Strand.PLUS)
    bare = search(SPACER, NGG, reference=reference, cache=cache)
    excluded = search(SPACER, NGG, reference=reference, on_target=on_target, cache=cache)
    assert len(cache) == 2  # distinct keys, not a collision
    # The on-target-excluding scan really dropped the self-match the bare scan kept.
    assert len(excluded.sites) < len(bare.sites)
