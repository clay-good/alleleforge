"""Tests for the sequence-embedding backbone protocol, stub, and cache."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from alleleforge.scoring.backbone import (
    CachedEmbedder,
    CaduceusEmbedder,
    Embedding,
    Evo2Embedder,
    NucleotideTransformerEmbedder,
    PersistentEmbeddingCache,
    SequenceEmbedder,
    StubEmbedder,
    sequence_hash,
)


class _CountingStub(StubEmbedder):
    """A stub that counts how many sequences actually reach :meth:`embed`."""

    def __init__(self, **kw: int) -> None:
        super().__init__(**kw)
        self.calls = 0

    def embed(self, sequences: Sequence[str]) -> list[Embedding]:
        self.calls += len(sequences)
        return super().embed(sequences)


class _CountingEmbedder:
    """A stub that records how many sequences it actually embedded."""

    name = "counting"
    version = "0"
    context_window = 64

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._stub = StubEmbedder(dim=4)

    def embed(self, sequences: Sequence[str]) -> list[Embedding]:
        self.calls.extend(sequences)
        return self._stub.embed(sequences)


def test_stub_is_deterministic_and_sized() -> None:
    emb = StubEmbedder(dim=6)
    a = emb.embed(["ACGTACGT"])
    b = emb.embed(["acgtacgt"])  # case-insensitive
    assert a == b
    assert len(a[0]) == 6
    assert all(-1.0 <= v <= 1.0 for v in a[0])


def test_stub_distinguishes_sequences() -> None:
    emb = StubEmbedder(dim=8)
    [u, v] = emb.embed(["AAAAAAAA", "TTTTTTTT"])
    assert u != v


def test_stub_satisfies_protocol() -> None:
    assert isinstance(StubEmbedder(), SequenceEmbedder)


def test_sequence_hash_is_case_insensitive() -> None:
    assert sequence_hash("ACGT") == sequence_hash("acgt")
    assert sequence_hash("ACGT") != sequence_hash("ACGA")


def test_cache_only_computes_misses() -> None:
    counter = _CountingEmbedder()
    cached = CachedEmbedder(counter)
    first = cached.embed(["ACGT", "TTTT", "ACGT"])  # ACGT repeated
    assert counter.calls == ["ACGT", "TTTT"]  # the duplicate was not recomputed
    assert cached.cache_size == 2
    second = cached.embed(["ACGT", "TTTT"])  # all cached now
    assert counter.calls == ["ACGT", "TTTT"]  # unchanged
    assert first[:2] == second


def test_cache_preserves_order_and_values() -> None:
    cached = CachedEmbedder(StubEmbedder(dim=4))
    seqs = ["GGGG", "CCCC", "AAAA"]
    assert cached.embed(seqs) == StubEmbedder(dim=4).embed(seqs)
    assert cached.name == "stub" and cached.version == "0" and cached.context_window == 512


def test_in_memory_cache_computes_each_sequence_once() -> None:
    stub = _CountingStub(dim=4)
    cached = CachedEmbedder(stub)
    cached.embed(["ACGT", "TTTT", "ACGT"])  # one repeat
    assert stub.calls == 2  # only the two distinct sequences reached embed()
    cached.embed(["ACGT", "TTTT"])  # both already cached
    assert stub.calls == 2


def test_persistent_cache_survives_across_runs(tmp_path: Path) -> None:
    # Two CachedEmbedder instances sharing a cache root stand in for two runs.
    stub1 = _CountingStub(dim=4)
    run1 = CachedEmbedder.persistent(stub1, root=tmp_path)
    first = run1.embed(["ACGT", "TTTT", "ACGT"])
    assert stub1.calls == 2 and run1.cache_size == 2

    stub2 = _CountingStub(dim=4)
    run2 = CachedEmbedder.persistent(stub2, root=tmp_path)
    second = run2.embed(["ACGT", "TTTT"])
    assert stub2.calls == 0  # served entirely from the on-disk cache of run 1
    assert second == first[:2]


def test_persistent_cache_is_scoped_per_embedder_identity(tmp_path: Path) -> None:
    # Different backbones must not read each other's embeddings for the same seq.
    a = PersistentEmbeddingCache("stub-0", root=tmp_path)
    b = PersistentEmbeddingCache("other-1", root=tmp_path)
    key = sequence_hash("ACGT")
    a[key] = (1.0, 2.0)
    assert key in a and key not in b
    assert a[key] == (1.0, 2.0)


def test_persistent_cache_missing_key_raises(tmp_path: Path) -> None:
    cache = PersistentEmbeddingCache("stub-0", root=tmp_path)
    with pytest.raises(KeyError):
        _ = cache["deadbeef"]


@pytest.mark.parametrize(
    ("cls", "name", "window"),
    [
        (NucleotideTransformerEmbedder, "nucleotide-transformer-v2-500m", 1000),
        (CaduceusEmbedder, "caduceus", 131072),
        (Evo2Embedder, "evo2", 8192),
    ],
)
def test_real_adapters_expose_metadata(cls: type, name: str, window: int) -> None:
    # Constructing the adapter needs no weights; embed() (gated by `real_weights`)
    # would lazily import torch. Here we only verify the interface contract.
    adapter = cls(torch_compile=True)
    assert adapter.name == name
    assert adapter.context_window == window
    assert adapter.model_id  # a HuggingFace model id is declared
    assert isinstance(adapter, SequenceEmbedder)
