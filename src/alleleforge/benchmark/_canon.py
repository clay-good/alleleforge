"""Canonical JSON serialization and content hashing for CRISPR-Bench.

Splits and datasets are **content-hashed** so a frozen split can prove on load
that neither its membership nor its underlying data has drifted. Both the
generator that mints a split and the loader that verifies it must agree byte for
byte on how an object becomes bytes, so that single definition lives here.

The rule is deliberately boring: sort keys, no insignificant whitespace, UTF-8.
A float is rendered by :func:`json.dumps`'s ``repr`` so two runs of CPython
produce identical bytes; this is the only place numbers cross into the hash.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Return a deterministic JSON string for ``obj``.

    Keys are sorted and separators are tight, so logically equal objects always
    serialize to identical bytes regardless of insertion order.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(obj: Any) -> str:
    """Return the SHA-256 hex digest of ``obj``'s canonical JSON encoding."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


#: Decimal places a float is rounded to before the reproducibility digest, so two
#: platforms that differ only in the last ULP (a KL/metric task) still agree. This
#: mirrors ``scripts/reproduce.py``'s tolerance for the design path.
DIGEST_FLOAT_PRECISION = 6


def _round_floats(obj: Any) -> Any:
    """Return ``obj`` with every float rounded to :data:`DIGEST_FLOAT_PRECISION`."""
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, DIGEST_FLOAT_PRECISION)
    return obj


def reproducibility_digest(scientific_body: Any) -> str:
    """Return a platform/release-stable digest of a result's *scientific* body.

    Unlike :func:`content_hash` (the same-artifact tamper seal, which covers the
    wall-clock timestamp, package version, and local config paths), this rounds
    every float to :data:`DIGEST_FLOAT_PRECISION` and hashes only the caller-chosen
    scientific body — metrics, model-card facts, task, split identity, dataset hash.
    So two independent runs of the same model on the same frozen ``(task, split)``
    produce the identical digest across releases and platforms, and a verifier can
    tell a genuine re-derivation from a coincidental version bump.
    """
    return content_hash(_round_floats(scientific_body))
