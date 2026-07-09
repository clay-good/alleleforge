"""Tests for the persistent, memory-mapped whole-genome FM-index (R4).

Correctness and engine-parity run everywhere (pure-Python build over tiny
contigs); the **scale** test — a downsampled chromosome built by the native SA-IS
kernel and queried over its memory map — is marked ``native`` and runs in the CI
rust job, where the linear-time build makes a hundreds-of-kilobases index fast.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from alleleforge.genome.index import FMIndex, GenomeIndex, native_sais_available
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import DNASequence

SPACER = "GACCATGCAACCTTGAACGT"
PAD = "T" * 12
NGG = PAM(pattern="NGG")


def _reference(tmp_path: Path, contigs: dict[str, str], name: str = "g.fa") -> ReferenceGenome:
    fasta = tmp_path / name
    fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
    return ReferenceGenome(fasta, build="hg38")


def test_indexes_every_contig_both_strands(tmp_path: Path) -> None:
    ref = _reference(tmp_path, {"chrA": PAD + SPACER + "TGG" + PAD, "chrB": "ACGT" * 8})
    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx")
    assert set(gi.contigs) == {"chrA", "chrB"}
    assert gi.build == "hg38"
    # The plus index matches a standalone FMIndex over the same contig.
    seq_a = PAD + SPACER + "TGG" + PAD
    standalone = FMIndex.build(seq_a, cache_dir=tmp_path / "fm", prefer_native=False)
    assert gi.locate("chrA", "TGG") == standalone.locate("TGG")
    assert [(h.protospacer_start, h.pam_start) for h in gi.pam_sites("chrA", NGG, 20)] == [
        (h.protospacer_start, h.pam_start) for h in standalone.pam_sites(NGG, 20)
    ]
    gi.close()
    standalone.close()


def test_minus_strand_index_is_the_reverse_complement(tmp_path: Path) -> None:
    contig = PAD + SPACER + "TGG" + PAD
    ref = _reference(tmp_path, {"chrA": contig})
    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx")
    rc = str(DNASequence(contig).reverse_complement())
    rc_index = FMIndex.build(rc, cache_dir=tmp_path / "fm", prefer_native=False)
    assert gi.minus("chrA").locate("ACGT") == rc_index.locate("ACGT")
    gi.close()
    rc_index.close()


def test_contigs_subset(tmp_path: Path) -> None:
    ref = _reference(tmp_path, {"chrA": "ACGTACGT", "chrB": "TTTTGGGG"})
    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx", contigs=["chrB"])
    assert gi.contigs == ("chrB",)
    gi.close()


def test_context_manager_closes(tmp_path: Path) -> None:
    ref = _reference(tmp_path, {"chrA": PAD + SPACER + "TGG" + PAD})
    with GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx") as gi:
        assert gi.locate("chrA", "TGG")


@pytest.mark.parametrize("mismatches", [4, 2, 0])
def test_engine_parity_with_and_without_genome_index(tmp_path: Path, mismatches: int) -> None:
    # A minus-strand site on chrB exercises both strand indexes.
    rc = str(DNASequence(SPACER).reverse_complement())
    ref = _reference(
        tmp_path,
        {"chrA": PAD + SPACER + "TGG" + PAD, "chrB": PAD + "CCA" + rc + PAD},
    )
    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx")
    plain = search(SPACER, NGG, reference=ref, mismatches=mismatches)
    indexed = search(SPACER, NGG, reference=ref, mismatches=mismatches, genome_index=gi)
    assert indexed.model_dump_json() == plain.model_dump_json()
    gi.close()


def test_search_rejects_genome_index_from_a_different_assembly(tmp_path: Path) -> None:
    # A genome_index built for one assembly, passed alongside a reference from
    # another, would anchor PAMs over the index's sequence while reading coordinates
    # from the reference — silently wrong hits. The engine fails closed instead.
    contigs = {"chrA": PAD + SPACER + "TGG" + PAD}
    ref_hg38 = _reference(tmp_path, contigs)  # build="hg38"
    gi = GenomeIndex.build_genome(ref_hg38, cache_dir=tmp_path / "idx")
    fasta = tmp_path / "grch37.fa"
    fasta.write_text("".join(f">{c}\n{s}\n" for c, s in contigs.items()))
    ref_grch37 = ReferenceGenome(fasta, build="GRCh37")
    with pytest.raises(ValueError, match="mismatched index"):
        search(SPACER, NGG, reference=ref_grch37, genome_index=gi)
    gi.close()


def test_cross_run_reuse_does_not_rebuild(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contigs = {"chrA": PAD + SPACER + "TGG" + PAD}
    ref = _reference(tmp_path, contigs)
    cache = tmp_path / "idx"
    GenomeIndex.build_genome(ref, cache_dir=cache).close()  # first run populates the cache

    # A second run (fresh process, same cache) must memory-map, never rebuild.
    import alleleforge.genome.index as index_mod

    def _fail_build(*args: object, **kwargs: object) -> None:
        raise AssertionError("rebuilt an already-cached contig index on resume")

    monkeypatch.setattr(index_mod.FMIndex, "_build_to_disk", staticmethod(_fail_build))
    ref2 = _reference(tmp_path, contigs, name="g2.fa")
    gi2 = GenomeIndex.build_genome(ref2, cache_dir=cache)  # must not call _build_to_disk
    assert gi2.locate("chrA", "TGG")
    gi2.close()


# --- scale: a downsampled chromosome, native SA-IS build, memory-mapped query ----

requires_native_sais = pytest.mark.skipif(
    not native_sais_available(), reason="native aforge_native SA-IS kernel not built"
)


@requires_native_sais
@pytest.mark.native
def test_scale_downsampled_chromosome_matches_linear_scan(tmp_path: Path) -> None:
    # ~300 kb "chromosome": large enough that the linear-time native build matters,
    # small enough to brute-force-check. The memory-mapped genome index must return
    # exactly the linear-scan reference result.
    rng = random.Random(20240501)
    chrom_seq = "".join(rng.choice("ACGT") for _ in range(300_000))
    ref = _reference(tmp_path, {"chr1": chrom_seq})

    gi = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx")  # in-memory=False -> mmap
    indexed = search(SPACER, NGG, reference=ref, genome_index=gi)
    linear = search(SPACER, NGG, reference=ref, use_fm_index=False)
    assert indexed.model_dump_json() == linear.model_dump_json()
    gi.close()

    # Cross-run: a fresh genome index over the same cache memory-maps and agrees.
    gi2 = GenomeIndex.build_genome(ref, cache_dir=tmp_path / "idx")
    assert search(SPACER, NGG, reference=ref, genome_index=gi2).model_dump_json() == (
        linear.model_dump_json()
    )
    gi2.close()
