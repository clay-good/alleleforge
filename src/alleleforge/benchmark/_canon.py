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
