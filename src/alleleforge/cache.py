"""Content-addressed caches that survive across runs (R4).

A run recomputes the same embeddings and the same reference off-target scans far
more often than it should — across a cohort, across re-runs, across a tuning
loop. This module is the **cross-run memo**: a small, dependency-free, disk-backed
key/value store, keyed by the SHA-256 of the inputs that determine the result, so
a value computed in one process is reused by the next.

Two properties make it safe to trust:

* **Content-addressed.** The key is a digest of every input that affects the
  result; a different input is a different key, never a stale hit. Callers that
  cannot fully capture their inputs in a key must not cache (the off-target cache
  enforces this — see :func:`alleleforge.offtarget.engine.search`).
* **Atomic writes.** Each value is written to a temp file and then renamed into
  place, so a crash or a concurrent writer can never leave a half-written entry a
  later read would trust (the cohort's parallel path relies on this).

Entries are sharded by the first two hex characters of the digest to keep any one
directory small at cohort/genome scale.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from alleleforge.config import get_settings

#: Bump to invalidate every cache after a breaking change to a stored format.
CACHE_FORMAT_VERSION = "1"

#: Suffix of the per-entry checksum sidecar written when a cache verifies on read.
_SUM_SUFFIX = ".sum"


class CacheIntegrityError(RuntimeError):
    """Raised when a verified cache entry's bytes do not match its stored checksum."""


def hash_parts(*parts: Any) -> str:
    """Return a stable SHA-256 hex digest over ``parts``.

    The parts are serialized as canonical JSON (sorted keys, no whitespace), so
    the digest is stable across processes and Python runs. Non-JSON values fall
    back to their ``str`` — pass only values whose ``str`` is itself stable.
    """
    blob = json.dumps(
        [CACHE_FORMAT_VERSION, *parts], sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(blob.encode()).hexdigest()


class ContentAddressedCache:
    """A sharded, atomically-written disk key/value store under the cache dir.

    Keys are hex digests (see :func:`hash_parts`); values are bytes (with JSON and
    text convenience wrappers). Construct one per logical namespace so unrelated
    caches never collide.
    """

    def __init__(
        self, namespace: str, *, root: str | Path | None = None, verify: bool = False
    ) -> None:
        """Open the cache for ``namespace`` under ``root`` (default: the cache dir).

        Args:
            namespace: A logical namespace so unrelated caches never collide.
            root: Override the cache root (default: the settings cache dir).
            verify: When ``True``, store a checksum sidecar with each entry and
                re-check the payload bytes against it on read, raising
                :class:`CacheIntegrityError` on a mismatch — for namespaces holding
                artifacts a corrupted-on-disk entry must never be served silently.
        """
        base = Path(root) if root is not None else get_settings().cache_dir
        self.root = base / "caches" / namespace
        self._verify = verify

    def _path(self, digest: str) -> Path:
        """Return the sharded on-disk path for ``digest``."""
        return self.root / digest[:2] / digest

    def __contains__(self, digest: str) -> bool:
        """Return ``True`` if ``digest`` is cached on disk."""
        return self._path(digest).exists()

    def get_bytes(self, digest: str) -> bytes | None:
        """Return the cached bytes for ``digest``, or ``None`` on a miss.

        Raises:
            CacheIntegrityError: If this cache verifies on read and the entry's
                bytes do not match its stored checksum (on-disk corruption or
                tampering).
        """
        path = self._path(digest)
        if not path.exists():
            return None
        data = path.read_bytes()
        if self._verify:
            sidecar = path.with_name(path.name + _SUM_SUFFIX)
            # A verify=True cache always writes a sidecar with each entry, so a
            # *missing* one is itself an integrity failure — an incomplete write or
            # a tamper that removed the checksum. Fail closed rather than serve the
            # unverifiable payload, else `rm *.sum` silently defeats the gate the
            # docstring promises ("a corrupted-on-disk entry must never be served").
            if not sidecar.exists():
                raise CacheIntegrityError(
                    f"cache entry {digest} failed integrity check (checksum sidecar is missing)"
                )
            expected = sidecar.read_text().strip()
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                raise CacheIntegrityError(
                    f"cache entry {digest} failed integrity check "
                    f"(expected {expected[:12]}…, got {actual[:12]}…)"
                )
        return data

    def put_bytes(self, digest: str, data: bytes) -> None:
        """Write ``data`` for ``digest`` atomically (temp file then rename)."""
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Unique temp name so concurrent writers of the same key never collide.
        # `id(data)` is only unique among *live* objects, so two threads writing the
        # same key with the same bytes object would collide on this name and the
        # loser's `replace` would race a FileNotFoundError; a per-call uuid is unique
        # regardless of the payload object's identity.
        token = f"{os.getpid()}.{uuid.uuid4().hex}"
        if self._verify:
            # Publish the checksum sidecar *before* the payload, each via its own
            # temp+rename. The read path (`get_bytes`) treats a present payload with
            # a missing sidecar as corruption and fails closed, so a payload must
            # never become visible ahead of its sidecar — otherwise a concurrent
            # reader raises CacheIntegrityError on a perfectly valid entry. A lone
            # sidecar is harmless: get_bytes returns None on the absent payload
            # before it ever looks for the sidecar. (Content-addressing guarantees a
            # re-put writes byte-identical data, so an updated sidecar can never
            # disagree with an already-published payload.)
            sidecar = path.with_name(path.name + _SUM_SUFFIX)
            stmp = sidecar.with_name(f"{sidecar.name}.{token}.tmp")
            stmp.write_text(hashlib.sha256(data).hexdigest())
            stmp.replace(sidecar)
        tmp = path.with_name(f"{path.name}.{token}.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)  # atomic on POSIX and Windows

    def get_text(self, digest: str) -> str | None:
        """Return the cached UTF-8 text for ``digest``, or ``None``."""
        data = self.get_bytes(digest)
        return data.decode() if data is not None else None

    def put_text(self, digest: str, text: str) -> None:
        """Write UTF-8 ``text`` for ``digest``."""
        self.put_bytes(digest, text.encode())

    def get_json(self, digest: str) -> Any | None:
        """Return the cached JSON value for ``digest``, or ``None``."""
        text = self.get_text(digest)
        return json.loads(text) if text is not None else None

    def put_json(self, digest: str, obj: Any) -> None:
        """Write ``obj`` as JSON for ``digest``."""
        self.put_text(digest, json.dumps(obj, separators=(",", ":")))

    def __len__(self) -> int:
        """Return the number of cached entries (scans the namespace)."""
        if not self.root.exists():
            return 0
        return sum(
            1
            for p in self.root.rglob("*")
            if p.is_file() and not p.name.endswith((".tmp", _SUM_SUFFIX))
        )
