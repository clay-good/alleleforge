"""Provenance must distinguish the genome a run searched.

Two designs over two different reference FASTAs produced **byte-identical**
provenance (timestamp aside) while their safety verdicts differed by nearly a
factor of two:

    a.fa   0 off-target sites   specificity 0.879
    b.fa   1 off-target site    specificity 0.468

`aforge verify` called both "provenance is complete and consistent". The reference
genome is the single largest determinant of an off-target result, and the block
recorded only `reference_build`, a *label* that stays `"hg38"` whatever FASTA is
handed to `--reference-fasta`. `_collect_datasets` records the reference only when it
carries a `DatasetVersion`, which happens for a registry-resolved build and not for a
plain FASTA — the ordinary, documented way to supply one.

The snapshot follows the convention `offtarget_regions` already set: a compact
`{contigs, bases, sha256}` descriptor rather than the input itself. It pins the
reference's *shape* — contig names and lengths — and says so in a `pins` field,
because two FASTAs with the same contigs and lengths and different bases are
indistinguishable to it, and a digest that quietly overclaims its own reach is the
failure this project spends its time preventing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.design.designer import _reference_snapshot, design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent


def _fasta(tmp_path: Path, name: str, extra: str = "") -> Path:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    path = tmp_path / name
    path.write_text(">chr2\n" + "".join(seq) + extra + "\n")
    return path


def _snapshot(fasta: Path) -> dict[str, object]:
    menu = design(
        "chr2:71:A>C",
        reference=ReferenceGenome(fasta),
        intent=EditIntent.INSTALL,
        max_candidates_per_chemistry=1,
    )
    assert menu.provenance is not None
    return dict(menu.provenance.config_snapshot)


def test_two_different_genomes_do_not_share_a_provenance(tmp_path: Path) -> None:
    """The finding itself: the same provenance must not describe two genomes."""
    plain = _snapshot(_fasta(tmp_path, "a.fa"))
    # The same locus plus a decoy copy of the protospacer: a different genome, and
    # the one whose specificity is halved.
    decoy = _snapshot(_fasta(tmp_path, "b.fa", "TATATATATATACCAATATA" + "TGG" + "T" * 20))
    assert plain["reference"] != decoy["reference"]


def test_the_same_genome_gives_the_same_descriptor(tmp_path: Path) -> None:
    """A digest that changed run to run would be noise, not identity."""
    # Two identical genomes written to two paths: the digest describes content,
    # not where the file happens to live.
    first = _snapshot(_fasta(tmp_path, "one.fa"))
    second = _snapshot(_fasta(tmp_path, "two.fa"))
    assert first["reference"] == second["reference"]


def test_the_descriptor_states_what_it_pins(tmp_path: Path) -> None:
    """It covers contig names and lengths, and says so rather than implying more."""
    ref = _snapshot(_fasta(tmp_path, "a.fa"))["reference"]
    assert isinstance(ref, dict)
    assert ref["contigs"] == 1
    assert ref["bases"] == 140
    assert isinstance(ref["sha256"], str) and len(ref["sha256"]) == 64
    assert "length" in str(ref["pins"]).lower()


def test_a_renamed_contig_changes_the_descriptor(tmp_path: Path) -> None:
    """Names are part of the identity: same length, different contig, different digest."""
    plain = _fasta(tmp_path, "plain.fa")
    renamed = tmp_path / "renamed.fa"
    renamed.write_text(plain.read_text().replace(">chr2", ">chr3"))
    # Taken from the descriptor directly: a chr3-only reference has no chr2:71 to
    # design against, and the point is the digest, not the design.
    before = _reference_snapshot(ReferenceGenome(plain))
    after = _reference_snapshot(ReferenceGenome(renamed))
    assert before["bases"] == after["bases"]
    assert before["sha256"] != after["sha256"]


@pytest.mark.parametrize("extra", ["", "TTTT"])
def test_contig_lengths_reads_the_index_not_the_sequence(tmp_path: Path, extra: str) -> None:
    """The lengths come from the FASTA index, so this stays O(contigs)."""
    ref = ReferenceGenome(_fasta(tmp_path, f"c{len(extra)}.fa", extra))
    assert ref.contig_lengths() == {"chr2": 140 + len(extra)}
