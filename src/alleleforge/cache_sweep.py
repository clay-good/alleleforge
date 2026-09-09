"""Sweep every on-disk store this tool would serve results from.

`aforge cache verify` was built here first and lived entirely in the CLI: a Python caller
holding a suspect cache directory — or the web API, or a deployment's own health check —
had no way to ask the question without reimplementing the walk. That is the library-vs-shell
gap this project treats as its most productive finding class, produced by the round that
*closed* the same gap for `FMIndex.verify()`.

The rule the round-442 entry states applies here too: "the library is the source of truth;
CLI and web are thin shells". The sweep is the truth; rendering it is the shell's job.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from alleleforge.cache import entry_status, stored_entries
from alleleforge.errors import reason

#: Statuses that mean a stored artifact is not what it should be.
FAILURES = frozenset({"CORRUPT", "UNREADABLE", "MISMATCH"})

#: Statuses that mean nothing was checked — neither a pass nor a failure.
UNCHECKED = frozenset({"unpinned", "not-cached", "unverifiable"})


@dataclass(frozen=True)
class CacheCheck:
    """One artifact's integrity result.

    Attributes:
        kind: The store it came from — a content-addressed namespace as it names itself
            on disk, or ``"fm-index"``, ``"dataset"``, ``"checkpoint"``.
        artifact: Which one: a digest, an index's content hash, a dataset or model name.
        status: ``"ok"`` (with an optional qualifier), one of :data:`FAILURES`, or one of
            :data:`UNCHECKED`.
        detail: What was found, when that needs saying.
    """

    kind: str
    artifact: str
    status: str
    detail: str = ""

    @property
    def failed(self) -> bool:
        """Return whether this artifact is not what it should be."""
        return self.status in FAILURES

    @property
    def checked(self) -> bool:
        """Return whether anything was actually established about it."""
        return self.status not in UNCHECKED


def _hashed(kind: str, artifact: str, path: Path, expected: str) -> CacheCheck:
    """Re-hash one pinned artifact at ``path`` against ``expected``.

    A missing file is ``not-cached``, not a failure: almost nothing in the registry ships
    or is downloaded by default, so absence is the ordinary state of most of the list —
    and reporting it as corruption would make the real failures unreadable.
    """
    if not path.is_file():
        return CacheCheck(kind, artifact, "not-cached", str(path))
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual == expected:
        return CacheCheck(kind, artifact, "ok")
    return CacheCheck(
        kind, artifact, "MISMATCH", f"{path}: expected {expected[:12]}…, got {actual[:12]}…"
    )


def verify_stores(root: str | Path, *, deep: bool = False) -> list[CacheCheck]:
    """Check every store under ``root`` and return one row per artifact.

    Args:
        root: The cache dir (the parent of ``caches/``, ``fm_index/``, ``data/``,
            ``models/``).
        deep: Also reconstruct each cached FM-index from its BWT and compare against the
            content hash recorded at build time. This is the only check that catches an
            index altered in place without changing its length, and it costs a full pass
            over the index — minutes on a whole-genome one.

    Returns:
        One :class:`CacheCheck` per artifact, in store order. Nothing is repaired or
        deleted: both work stores are content-addressed and both artifact stores are
        pinned, so removing a named entry is always safe, and which to remove is the
        operator's call.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.genome.index import FMIndex, FMIndexIntegrityError
    from alleleforge.model_zoo.registry import default_registry

    cache_root = Path(root)
    checks: list[CacheCheck] = []

    # Every content-addressed namespace on disk, not the ones this function remembers.
    for namespace, path in stored_entries(cache_root):
        status, detail = entry_status(path)
        checks.append(CacheCheck(namespace, path.name, status, detail))

    index_root = cache_root / "fm_index"
    for meta in sorted(index_root.glob("*/meta.json")) if index_root.is_dir() else []:
        entry = meta.parent
        try:
            index = FMIndex.load(entry)
            if deep:
                index.verify()
        except FMIndexIntegrityError as exc:
            checks.append(CacheCheck("fm-index", entry.name, "CORRUPT", reason(exc)))
        except Exception as exc:  # noqa: BLE001 - an unloadable index is a failed index
            checks.append(
                CacheCheck(
                    "fm-index", entry.name, "UNREADABLE", f"{type(exc).__name__}: {reason(exc)}"
                )
            )
        else:
            checks.append(
                CacheCheck("fm-index", entry.name, "ok" if deep else "ok (structure only)")
            )

    # The two artifact stores. A pinned dataset or checkpoint is re-hashed on every
    # resolve already, so this adds no new *rule* — only the ability to ask before a run
    # rather than finding out during one.
    for name in DEFAULT_REGISTRY.names:
        descriptor = DEFAULT_REGISTRY.get(name)
        if descriptor.sha256 is None:
            checks.append(CacheCheck("dataset", name, "unpinned", "no checksum to check"))
            continue
        # Bundled bytes live in the installed package, never in the cache — checking the
        # cache path for them is how a dataset that is always present came to be reported
        # unavailable once already.
        bundled = descriptor.bundled_file()
        path = (
            bundled
            if bundled is not None
            else DEFAULT_REGISTRY.cache_path(name, cache_dir=cache_root / "data")
        )
        checks.append(_hashed("dataset", name, path, descriptor.sha256))

    zoo = default_registry()
    for name in zoo.names:
        card = zoo.get(name)
        if card.checkpoint_sha256 is None:
            checks.append(CacheCheck("checkpoint", name, "unpinned", "no checksum to check"))
            continue
        path = cache_root / "models" / f"{card.name}.{card.version}.ckpt"
        checks.append(
            _hashed("checkpoint", f"{card.name}.{card.version}", path, card.checkpoint_sha256)
        )
    return checks


def held_bytes(root: str | Path) -> dict[str, int]:
    """Return the bytes each on-disk store under ``root`` holds, largest first.

    **Nothing evicts these.** Both cross-run caches are content-addressed and append-only
    by design — a changed input is a new key, which is what makes a stale hit impossible
    and also means the old entry stays forever. An FM-index over a whole genome runs to
    several gigabytes per contig-strand, and editing the reference mints a new one beside
    the old rather than replacing it. That is the right correctness trade and the wrong
    thing to leave invisible.
    """
    cache_root = Path(root)
    sizes: dict[str, int] = {}
    for store in ("caches", "fm_index", "data", "models"):
        directory = cache_root / store
        if not directory.is_dir():
            continue
        total = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
        if total:
            sizes[store] = total
    return dict(sorted(sizes.items(), key=lambda item: -item[1]))
