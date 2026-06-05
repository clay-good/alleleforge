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
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from alleleforge.cache import ContentAddressedCache
from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import Downloader, ModelRegistry, ModelUse

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


class EmbeddingCache(Protocol):
    """The minimal mapping :class:`CachedEmbedder` needs from its backing store.

    A plain ``dict[str, Embedding]`` satisfies it (the in-process default); the
    cross-run :class:`PersistentEmbeddingCache` satisfies it too, so the embedder
    is agnostic to where embeddings are memoized.
    """

    def __contains__(self, key: str) -> bool:
        """Return ``True`` if ``key`` is cached."""
        ...

    def __getitem__(self, key: str) -> Embedding:
        """Return the cached embedding for ``key``."""
        ...

    def __setitem__(self, key: str, value: Embedding) -> None:
        """Cache ``value`` under ``key``."""
        ...

    def __len__(self) -> int:
        """Return the number of cached embeddings."""
        ...


def sequence_hash(sequence: str) -> str:
    """Return the SHA-256 hex digest of an upper-cased sequence (cache key)."""
    return hashlib.sha256(sequence.upper().encode()).hexdigest()


class PersistentEmbeddingCache:
    """A cross-run embedding cache backed by the content-addressed disk store.

    Keys are sequence hashes; values are stored as JSON float lists under a
    namespace scoped to the embedder identity, so an embedding computed in one run
    is reused by the next and two different backbones never collide. Satisfies
    :class:`EmbeddingCache`.
    """

    def __init__(self, embedder_id: str, *, root: str | Path | None = None) -> None:
        """Open the persistent cache for ``embedder_id`` (e.g. ``"stub-0"``)."""
        self._store = ContentAddressedCache(f"embeddings/{embedder_id}", root=root)

    def __contains__(self, key: str) -> bool:
        """Return ``True`` if ``key``'s embedding is on disk."""
        return key in self._store

    def __getitem__(self, key: str) -> Embedding:
        """Return the on-disk embedding for ``key`` (raises ``KeyError`` on miss)."""
        data = self._store.get_json(key)
        if data is None:
            raise KeyError(key)
        return tuple(data)

    def __setitem__(self, key: str, value: Embedding) -> None:
        """Persist ``value`` under ``key``."""
        self._store.put_json(key, list(value))

    def __len__(self) -> int:
        """Return the number of cached embeddings on disk."""
        return len(self._store)


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
    """Wrap a :class:`SequenceEmbedder`, memoizing results by sequence hash.

    The backing store is any :class:`EmbeddingCache` — an in-process ``dict`` by
    default, or :meth:`persistent` for a cross-run, content-addressed disk cache.
    """

    def __init__(self, embedder: SequenceEmbedder, *, cache: EmbeddingCache | None = None):
        """Wrap ``embedder``; share or seed an optional ``cache`` (default: dict)."""
        self._embedder = embedder
        self._cache: EmbeddingCache = cache if cache is not None else {}

    @classmethod
    def persistent(
        cls, embedder: SequenceEmbedder, *, root: str | Path | None = None
    ) -> CachedEmbedder:
        """Wrap ``embedder`` with a cross-run disk cache scoped to its identity."""
        embedder_id = f"{embedder.name}-{embedder.version}"
        return cls(embedder, cache=PersistentEmbeddingCache(embedder_id, root=root))

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


class _HuggingFaceEmbedder(WeightGate):
    """Shared mean-pooled HuggingFace transformer embedder (lazy, optional).

    Weights are resolved through the **consent-gated, license-checked model zoo**
    (:meth:`~alleleforge.model_zoo.loader.WeightGate.resolve_weights`), not a bare
    ``from_pretrained(model_id)``: loading a real backbone requires explicit
    consent and a license that permits the use, and the resolved
    :class:`ModelCheckpoint` is recorded for provenance. The consent/license/checksum
    flow is exercisable without torch or the network (an injected downloader); only
    the tensor load in :meth:`embed` needs the ``ml`` extra and real weights.
    """

    name = "hf"
    version = "0"
    model_id = ""
    context_window = 1000

    def __init__(
        self,
        *,
        device: str = "cpu",
        torch_compile: bool = False,
        registry: ModelRegistry | None = None,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        cache_dir: str | Path | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        """Configure device, the model-zoo gate, and consent for weight download.

        Args:
            device: Torch device for inference (``"cpu"``/``"cuda"``).
            torch_compile: Whether to ``torch.compile`` the loaded model.
            registry: Model-zoo registry (defaults to the bundled cards).
            use: The use the weights are loaded for (drives the license gate).
            consent: Must be ``True`` to authorize any weight download.
            cache_dir: Override for the checkpoint cache (pinned-artifact path).
            downloader: Injected fetcher for the pinned-artifact path (tests).
        """
        super().__init__(
            registry=registry,
            use=use,
            consent=consent,
            cache_dir=cache_dir,
            downloader=downloader,
        )
        self.device = device
        self.torch_compile = torch_compile
        self._model: Any = None
        self._tokenizer: Any = None

    def _load(self) -> None:  # pragma: no cover - requires weights
        """Lazily resolve weights (consent-gated) and load the tokenizer + model."""
        torch, auto_model, auto_tokenizer = _require_transformers()
        target = self.resolve_weights() or self.model_id
        self._tokenizer = auto_tokenizer.from_pretrained(target)
        model = auto_model.from_pretrained(target).to(self.device).eval()
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
    card_name = "nucleotide-transformer-v2-500m"
    context_window = 1000


class CaduceusEmbedder(_HuggingFaceEmbedder):
    """Caduceus bi-directional long-context DNA backbone (optional)."""

    name = "caduceus"
    version = "1.0"
    model_id = "kuleshov-group/caduceus-ps_seqlen-131k_d_model-256_n_layer-16"
    card_name = "caduceus"
    context_window = 131072


class Evo2Embedder(_HuggingFaceEmbedder):
    """Evo 2 genomic foundation model backbone (optional)."""

    name = "evo2"
    version = "2.0"
    model_id = "arcinstitute/evo2_7b"
    card_name = "evo2"
    context_window = 8192
