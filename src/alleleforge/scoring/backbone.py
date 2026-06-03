"""Sequence-backbone embeddings behind one swappable protocol.

A :class:`SequenceEmbedder` maps DNA sequences to fixed-width vectors that
downstream guide-efficiency and outcome models consume. The default production
backbone is **Nucleotide Transformer v2 (500M)**; Caduceus and Evo 2 adapters sit
behind the same protocol (interface mandatory, full implementation optional and
gated behind the ``real_weights`` test marker).

CI never downloads a 500M-parameter model. :class:`StubEmbedder` produces
deterministic, content-derived pseudo-embeddings so the embedding cache, the
out-of-distribution detector, and the uncertainty machinery are all exercisable
without any weights. :class:`CachedEmbedder` memoizes by sequence hash so a
sequence is never embedded twice.

Embeddings are plain ``tuple[float, ...]`` here (no numpy/torch dependency in the
core path); the real adapters return the same shape from their tensor backends.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

#: A single fixed-width embedding vector.
Embedding = tuple[float, ...]


@runtime_checkable
class SequenceEmbedder(Protocol):
    """Anything that embeds DNA sequences into fixed-width vectors."""

    name: str
    version: str
    context_window: int

    def embed(self, sequences: Sequence[str]) -> list[Embedding]:
        """Return one embedding per input sequence (order preserved)."""
        ...


def sequence_hash(sequence: str) -> str:
    """Return the SHA-256 hex digest of an upper-cased sequence (cache key)."""
    return hashlib.sha256(sequence.upper().encode()).hexdigest()


class StubEmbedder:
    """A deterministic, weight-free embedder for tests and CI.

    Each output dimension is derived from the SHA-256 of the sequence (salted by
    the dimension index), giving a stable, content-sensitive vector in ``[-1, 1]``.
    Identical sequences embed identically; different sequences almost never
    collide. This is **not** a biological model — it exists so the cache, OOD
    detector, and uncertainty code can be tested without real weights.
    """

    name = "stub"
    version = "0"

    def __init__(self, *, dim: int = 8, context_window: int = 512) -> None:
        """Configure the embedding dimension and nominal context window."""
        self.dim = dim
        self.context_window = context_window

    def _vector(self, sequence: str) -> Embedding:
        """Return the deterministic vector for one sequence."""
        seq = sequence.upper()
        values: list[float] = []
        for i in range(self.dim):
            digest = hashlib.sha256(f"{i}:{seq}".encode()).digest()
            (raw,) = struct.unpack_from(">I", digest)  # first 4 bytes -> uint32
            values.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)  # map to [-1, 1]
        return tuple(values)

    def embed(self, sequences: Sequence[str]) -> list[Embedding]:
        """Return deterministic pseudo-embeddings for ``sequences``."""
        return [self._vector(s) for s in sequences]


class CachedEmbedder:
    """Wrap a :class:`SequenceEmbedder`, memoizing results by sequence hash."""

    def __init__(self, embedder: SequenceEmbedder, *, cache: dict[str, Embedding] | None = None):
        """Wrap ``embedder``; share or seed an optional ``cache`` dict."""
        self._embedder = embedder
        self._cache: dict[str, Embedding] = cache if cache is not None else {}

    @property
    def name(self) -> str:
        """Return the wrapped embedder's name."""
        return self._embedder.name

    @property
    def version(self) -> str:
        """Return the wrapped embedder's version."""
        return self._embedder.version

    @property
    def context_window(self) -> int:
        """Return the wrapped embedder's context window."""
        return self._embedder.context_window

    @property
    def cache_size(self) -> int:
        """Return the number of cached sequences."""
        return len(self._cache)

    def embed(self, sequences: Sequence[str]) -> list[Embedding]:
        """Return embeddings, computing only the distinct cache misses."""
        seen: set[str] = set()
        misses: list[str] = []
        for s in sequences:
            key = sequence_hash(s)
            if key not in self._cache and key not in seen:
                seen.add(key)
                misses.append(s)
        if misses:
            for seq, vec in zip(misses, self._embedder.embed(misses), strict=True):
                self._cache[sequence_hash(seq)] = vec
        return [self._cache[sequence_hash(s)] for s in sequences]


def _require_transformers() -> Any:  # pragma: no cover - requires the ml extra
    """Import torch + transformers, or raise a helpful error if missing."""
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "real backbone embedders require the 'ml' extra (torch, transformers); "
            "install alleleforge[ml] or use StubEmbedder in tests"
        ) from exc
    return torch, AutoModel, AutoTokenizer


class _HuggingFaceEmbedder:
    """Shared mean-pooled HuggingFace transformer embedder (lazy, optional)."""

    name = "hf"
    version = "0"
    model_id = ""
    context_window = 1000

    def __init__(self, *, device: str = "cpu", torch_compile: bool = False) -> None:
        """Configure device and whether to ``torch.compile`` the model."""
        self.device = device
        self.torch_compile = torch_compile
        self._model: Any = None
        self._tokenizer: Any = None

    def _load(self) -> None:  # pragma: no cover - requires weights
        """Lazily load the tokenizer and model (downloads weights on first use)."""
        torch, auto_model, auto_tokenizer = _require_transformers()
        self._tokenizer = auto_tokenizer.from_pretrained(self.model_id)
        model = auto_model.from_pretrained(self.model_id).to(self.device).eval()
        self._model = torch.compile(model) if self.torch_compile else model

    def embed(self, sequences: Sequence[str]) -> list[Embedding]:  # pragma: no cover - needs ml
        """Return mean-pooled last-hidden-state embeddings for ``sequences``."""
        torch, _, _ = _require_transformers()
        if self._model is None:
            self._load()
        out: list[Embedding] = []
        for seq in sequences:
            ids = self._tokenizer(
                seq, return_tensors="pt", truncation=True, max_length=self.context_window
            ).to(self.device)
            with torch.no_grad():
                hidden = self._model(**ids).last_hidden_state  # (1, L, H)
            vec = hidden.mean(dim=1).squeeze(0).tolist()
            out.append(tuple(float(v) for v in vec))
        return out

    def export_onnx(self, path: str) -> None:  # pragma: no cover - requires weights
        """Export the loaded model to ONNX (optional acceleration path)."""
        raise NotImplementedError("ONNX export is wired up alongside the real-weights path")


class NucleotideTransformerEmbedder(_HuggingFaceEmbedder):
    """Nucleotide Transformer v2 (500M) — the default production backbone."""

    name = "nucleotide-transformer-v2-500m"
    version = "2.0"
    model_id = "InstaDeepAI/nucleotide-transformer-v2-500m-multi-species"
    context_window = 1000


class CaduceusEmbedder(_HuggingFaceEmbedder):
    """Caduceus bi-directional long-context DNA backbone (optional)."""

    name = "caduceus"
    version = "1.0"
    model_id = "kuleshov-group/caduceus-ps_seqlen-131k_d_model-256_n_layer-16"
    context_window = 131072


class Evo2Embedder(_HuggingFaceEmbedder):
    """Evo 2 genomic foundation model backbone (optional)."""

    name = "evo2"
    version = "2.0"
    model_id = "arcinstitute/evo2_7b"
    context_window = 8192
