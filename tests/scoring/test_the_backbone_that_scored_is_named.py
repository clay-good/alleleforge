"""A run scored through a real sequence backbone recorded the ensemble card alone.

`EnsembleEfficiencyScorer` is a set of projection heads *over an embedding*. On the
weight-free stub that is the whole story. With a real backbone — Nucleotide Transformer,
Caduceus, Evo2, each with its own card, licence and pinned checksum, each resolved through
the consent-gated model zoo — the embedding is what the numbers are made of, and
`_HuggingFaceEmbedder`'s own docstring says "the resolved `ModelCheckpoint` is recorded
for provenance".

It was not. `backbone_checkpoint()` exists, says "for provenance" in its first line, and
had no caller anywhere in the package: `cas9_model_checkpoints` stamped
`efficiency.model_card()` and stopped. A menu scored by gated, licence-checked,
checksum-pinned weights named none of them, which is precisely the claim the provenance
block exists to make.

And the way a real backbone is meant to be used made it worse:
`CachedEmbedder.persistent(NucleotideTransformerEmbedder())` is the documented shape, and
the wrapper forwarded `name`, `version` and `context_window` but not `model_checkpoint` —
so even a caller who asked got `None`.
"""

from __future__ import annotations

from typing import Any

from alleleforge.design.cas9 import cas9_model_checkpoints
from alleleforge.scoring.backbone import CachedEmbedder, StubEmbedder
from alleleforge.scoring.cas9_efficiency import EnsembleEfficiencyScorer
from alleleforge.types.provenance import ModelCheckpoint

_BACKBONE = ModelCheckpoint(
    name="nucleotide-transformer-v2-500m",
    version="2.0",
    sha256="f" * 64,
    chemistry=None,
    license="CC-BY-NC-SA-4.0",
    citation="Dalla-Torre et al.",
    intended_use="Sequence embedding.",
    out_of_scope_use="Clinical decision-making.",
    known_failure_modes=("Trained on a fixed context window.",),
)


class _WeightedEmbedder(StubEmbedder):  # type: ignore[misc]
    """A stub that reports a resolved checkpoint, as a real backbone does."""

    def model_checkpoint(self) -> ModelCheckpoint | None:
        return _BACKBONE


def _names(checkpoints: tuple[Any, ...]) -> list[str]:
    return [c.name for c in checkpoints]


def test_the_stub_backbone_adds_nothing() -> None:
    """The floor: a weight-free embedder has no checkpoint, and must not invent one."""
    names = _names(cas9_model_checkpoints(EnsembleEfficiencyScorer(embedder=StubEmbedder(dim=16))))
    assert "cas9-efficiency-ensemble" in names
    assert not [n for n in names if "nucleotide" in n]


def test_a_resolved_backbone_is_named_in_provenance() -> None:
    scorer = EnsembleEfficiencyScorer(embedder=_WeightedEmbedder(dim=16))
    names = _names(cas9_model_checkpoints(scorer))
    assert "cas9-efficiency-ensemble" in names, names
    assert "nucleotide-transformer-v2-500m" in names, names


def test_the_cache_wrapper_does_not_hide_it() -> None:
    """The documented way to use a real backbone is through this wrapper."""
    wrapped = CachedEmbedder(_WeightedEmbedder(dim=16))
    assert wrapped.model_checkpoint() == _BACKBONE
    scorer = EnsembleEfficiencyScorer(embedder=wrapped)
    assert scorer.backbone_checkpoint() == _BACKBONE
    assert "nucleotide-transformer-v2-500m" in _names(cas9_model_checkpoints(scorer))


def test_the_wrapper_around_a_weight_free_embedder_still_says_nothing() -> None:
    assert CachedEmbedder(StubEmbedder(dim=16)).model_checkpoint() is None


def test_a_design_records_it_end_to_end(tmp_path: Any) -> None:
    """Through `design()`, which is where a reader meets the provenance block."""
    from alleleforge.design.designer import design
    from alleleforge.genome.reference import ReferenceGenome
    from alleleforge.types.edit import Chemistry, EditIntent

    fasta = tmp_path / "cas9.fa"
    spacer = "ACGTAACGTTACGTAACGTT"
    fasta.write_text(">chr1\n" + "T" * 20 + spacer + "TGG" + "T" * 20 + "\n")
    reference = ReferenceGenome(fasta, build="hg38")
    menu = design(
        "chr1:31:A>G",
        reference=reference,
        # Asked for by name: a break-free route exists here, and the nuclease vertical is
        # offered only when none does — which is the routing this file is not about.
        chemistries=[Chemistry.CAS9_NUCLEASE],
        intent=EditIntent.KNOCK_OUT,
        run_offtarget=False,
        cas9_efficiency_scorer=EnsembleEfficiencyScorer(embedder=_WeightedEmbedder(dim=16)),
    )
    recorded = [m.name for m in menu.provenance.models]
    if "cas9-efficiency-ensemble" not in recorded:  # pragma: no cover - fixture guard
        raise AssertionError(f"the nuclease vertical did not run: {recorded}")
    assert "nucleotide-transformer-v2-500m" in recorded, recorded
