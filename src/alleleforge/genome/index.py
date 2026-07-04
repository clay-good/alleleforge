"""FM-index over reference sequence for PAM-anchored candidate search.

The performance-critical FM-index lives in the Rust ``aforge_native`` crate
(``bwt.rs``). That crate is **optional**: when it is not built, this module
provides a *correct* pure-Python FM-index behind the same interface, mirroring
how :mod:`alleleforge._native` degrades. CI never blocks on the native build.

The index is **content-addressed** (keyed by the SHA-256 of the indexed text)
and cached on disk. By default the BWT is **memory-mapped** from the cache so a
large index does not pin its whole footprint in RAM; pass ``in_memory=True`` to
load it eagerly into a Python string instead.

On-disk size, for scale: hg38's primary assembly is ~3.1 Gb of sequence, so a
single-strand FM-index built this way is on the order of several gigabytes on
disk. :meth:`FMIndex.build` warns before constructing an index over a sequence
larger than :data:`SIZE_WARN_THRESHOLD`.
"""

from __future__ import annotations

import hashlib
import json
import mmap
import warnings
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING, cast

from alleleforge import _native
from alleleforge.config import get_settings
from alleleforge.types.guide import PAM
from alleleforge.types.sequence import (
    IUPAC_EXPAND,
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
)

if TYPE_CHECKING:
    from types import TracebackType

    from alleleforge.genome.reference import ReferenceGenome

#: Allowed characters in an indexed reference sequence (the four bases + ``N``).
_INDEX_ALPHABET = frozenset("ACGTN")

#: Sentinel terminator, sorted before every base. Never appears in input.
_SENTINEL = "\x00"

#: Warn before building an index over a sequence larger than this (bases).
SIZE_WARN_THRESHOLD = 50_000_000


class FMIndexIntegrityError(RuntimeError):
    """Raised when a cached FM-index does not reconstruct to its recorded content hash."""


#: Default checkpoint spacing for the rank (occ) table.
_DEFAULT_OCC_RATE = 64

#: Default sampling rate for the suffix array (locate step budget).
_DEFAULT_SA_RATE = 32


def native_fm_available() -> bool:
    """Return ``True`` if the native crate exposes the FM-index kernels.

    The Phase 0 crate only ships ``version()``; the ``bwt`` kernels arrive
    later. Until then this is ``False`` and the pure-Python path is used.
    """
    ext = getattr(_native, "_ext", None)
    return _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "fm_locate")


def native_sais_available() -> bool:
    """Return ``True`` if the native crate exposes the SA-IS suffix-array kernel."""
    ext = getattr(_native, "_ext", None)
    return _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "fm_suffix_array")


def _suffix_array(s: str, data: str, n: int) -> list[int]:
    """Return the suffix array of ``data`` (``s`` + sentinel), native when built.

    The native SA-IS kernel builds it in linear time; the pure-Python fallback is
    the direct sort. The unique sentinel makes every suffix distinct, so the two
    are byte-identical (pinned by ``tests/genome/test_native.py``).
    """
    if native_sais_available():  # pragma: no cover - native not built in the CI test matrix
        return list(_native._ext.fm_suffix_array(s))  # type: ignore[attr-defined]
    return sorted(range(n), key=lambda i: data[i:])


@dataclass(frozen=True)
class PamHit:
    """A PAM-anchored protospacer placement on the indexed (plus) strand.

    Coordinates are 0-based half-open offsets into the indexed text. A SpCas9
    site is laid out ``5'-[protospacer][PAM]-3'``, so the protospacer occupies
    ``[protospacer_start, pam_start)`` and the PAM ``[pam_start, pam_end)``.

    Attributes:
        protospacer_start: Start of the protospacer.
        pam_start: Start of the PAM (also the protospacer end).
        pam_end: End of the PAM.
        pam_sequence: The concrete PAM bases read from the reference.
    """

    protospacer_start: int
    pam_start: int
    pam_end: int
    pam_sequence: str


def _expand_pam(pam: PAM) -> list[str]:
    """Expand an IUPAC PAM pattern into its concrete ACGT instantiations."""
    choices = [sorted(IUPAC_EXPAND[code]) for code in pam.pattern]
    return ["".join(combo) for combo in product(*choices)]


class FMIndex:
    """A content-addressed FM-index supporting exact and PAM-anchored search.

    Build one with :meth:`build` (which caches it on disk) or load an existing
    cache directory with :meth:`load`. Backward search drives :meth:`count`,
    :meth:`locate`, and :meth:`pam_sites`.
    """

    def __init__(
        self,
        *,
        length: int,
        c_table: dict[str, int],
        occ: dict[str, list[int]],
        occ_rate: int,
        sa_samples: dict[int, int],
        content_hash: str,
        bwt: str | None = None,
        mm: mmap.mmap | None = None,
    ) -> None:
        """Initialise from already-built tables (see :meth:`build` / :meth:`load`)."""
        self.length = length
        self.c_table = c_table
        self._occ = occ
        self._occ_rate = occ_rate
        self._sa_samples = sa_samples
        self.content_hash = content_hash
        self._bwt = bwt
        self._mm = mm

    # -- construction -------------------------------------------------------

    @classmethod
    def build(
        cls,
        text: str | DNASequence,
        *,
        cache_dir: str | Path | None = None,
        in_memory: bool = False,
        rebuild: bool = False,
        occ_rate: int = _DEFAULT_OCC_RATE,
        sa_rate: int = _DEFAULT_SA_RATE,
        prefer_native: bool = True,
    ) -> FMIndex:
        """Build (or load from cache) an FM-index over ``text``.

        Args:
            text: Reference sequence over ``ACGTN``.
            cache_dir: Override for the index cache root.
            in_memory: Load the BWT fully into RAM instead of memory-mapping it.
            rebuild: Rebuild even if a cached index already exists.
            occ_rate: Checkpoint spacing for the rank table.
            sa_rate: Suffix-array sampling rate.
            prefer_native: Use the Rust kernels when they are built.

        Returns:
            A ready-to-query :class:`FMIndex`.

        Raises:
            ValueError: If ``text`` is empty or contains non-``ACGTN`` bases.
        """
        if prefer_native and native_fm_available():  # pragma: no cover - native not built in CI
            ext = _native._ext  # type: ignore[attr-defined]  # optional native kernel
            return cast("FMIndex", ext.fm_build(str(text)))
        s = str(text).upper()
        if not s:
            raise ValueError("cannot index an empty sequence")
        bad = set(s) - _INDEX_ALPHABET
        if bad:
            raise ValueError(f"index alphabet is ACGTN; got disallowed {sorted(bad)}")
        if len(s) > SIZE_WARN_THRESHOLD:
            warnings.warn(
                f"building an FM-index over {len(s):,} bases; expect a multi-gigabyte "
                "on-disk index (hg38 single-strand is several GB)",
                stacklevel=2,
            )
        content_hash = hashlib.sha256(s.encode()).hexdigest()
        cache = cls._cache_path(content_hash, cache_dir)
        if rebuild or not (cache / "meta.json").exists():
            cls._build_to_disk(s, cache, occ_rate, sa_rate, content_hash)
        return cls.load(cache, in_memory=in_memory)

    @staticmethod
    def _cache_path(content_hash: str, cache_dir: str | Path | None) -> Path:
        """Return the content-addressed cache directory for ``content_hash``."""
        root = Path(cache_dir) if cache_dir is not None else get_settings().cache_dir / "fm_index"
        return root / content_hash

    @staticmethod
    def _build_to_disk(s: str, cache: Path, occ_rate: int, sa_rate: int, content_hash: str) -> None:
        """Construct the BWT, rank table and sampled SA, and persist them."""
        data = s + _SENTINEL
        n = len(data)
        # Suffix array: the native SA-IS kernel (O(n)) when the crate is built —
        # this is what makes the on-disk, memory-mapped index scale to whole
        # chromosomes; otherwise the pure-Python direct sort (O(n^2 log n), fine for
        # the small contigs CI builds without the crate). Both yield the identical
        # SA (the unique sentinel makes every suffix distinct), pinned by parity.
        suffix_array = _suffix_array(s, data, n)
        bwt = "".join(data[(i - 1) % n] for i in suffix_array)

        alphabet = sorted(set(data))
        counts = {c: bwt.count(c) for c in alphabet}
        c_table: dict[str, int] = {}
        running = 0
        for c in alphabet:
            c_table[c] = running
            running += counts[c]

        n_checkpoints = n // occ_rate + 1
        occ: dict[str, list[int]] = {c: [0] * n_checkpoints for c in alphabet}
        seen = {c: 0 for c in alphabet}
        for k in range(n_checkpoints):
            for c in alphabet:
                occ[c][k] = seen[c]
            for j in range(k * occ_rate, min((k + 1) * occ_rate, n)):
                seen[bwt[j]] += 1

        sa_samples = {row: pos for row, pos in enumerate(suffix_array) if pos % sa_rate == 0}

        cache.mkdir(parents=True, exist_ok=True)
        (cache / "bwt.bin").write_bytes(bwt.encode("latin-1"))
        (cache / "occ.json").write_text(json.dumps(occ))
        (cache / "sa.json").write_text(json.dumps({str(k): v for k, v in sa_samples.items()}))
        (cache / "meta.json").write_text(
            json.dumps(
                {
                    "length": n,
                    "c_table": c_table,
                    "occ_rate": occ_rate,
                    "sa_rate": sa_rate,
                    "content_hash": content_hash,
                }
            )
        )

    @classmethod
    def load(cls, cache: str | Path, *, in_memory: bool = False) -> FMIndex:
        """Load an FM-index from a content-addressed cache directory.

        Args:
            cache: The directory written by :meth:`build`.
            in_memory: Read the BWT into RAM instead of memory-mapping it.
        """
        cache = Path(cache)
        meta = json.loads((cache / "meta.json").read_text())
        occ = {c: list(v) for c, v in json.loads((cache / "occ.json").read_text()).items()}
        sa_samples = {int(k): v for k, v in json.loads((cache / "sa.json").read_text()).items()}
        bwt_path = cache / "bwt.bin"
        bwt: str | None = None
        mm: mmap.mmap | None = None
        if in_memory:
            bwt = bwt_path.read_bytes().decode("latin-1")
        else:
            # The mmap keeps the mapping alive after the fd is closed; the `with`
            # closes the fd on success *and* releases it if mmap construction
            # raises (a corrupt cache, ENOMEM), rather than leaking the handle.
            with bwt_path.open("rb") as fh:
                mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        return cls(
            length=meta["length"],
            c_table=meta["c_table"],
            occ=occ,
            occ_rate=meta["occ_rate"],
            sa_samples=sa_samples,
            content_hash=meta["content_hash"],
            bwt=bwt,
            mm=mm,
        )

    # -- BWT access ---------------------------------------------------------

    def _slice(self, lo: int, hi: int) -> str:
        """Return ``bwt[lo:hi]`` as a string from RAM or the memory map."""
        if self._bwt is not None:
            return self._bwt[lo:hi]
        assert self._mm is not None
        return self._mm[lo:hi].decode("latin-1")

    def _char_at(self, i: int) -> str:
        """Return the single BWT character at row ``i``."""
        return self._slice(i, i + 1)

    def _rank(self, c: str, i: int) -> int:
        """Return the number of ``c`` in ``bwt[:i]`` (occ checkpoints + remainder)."""
        if i <= 0:
            return 0
        k = i // self._occ_rate
        base = self._occ[c][k]
        return base + self._slice(k * self._occ_rate, i).count(c)

    def _bw_search(self, pattern: str) -> tuple[int, int]:
        """Return the half-open BWT row range ``[lo, hi)`` matching ``pattern``."""
        lo, hi = 0, self.length
        for ch in reversed(pattern):
            if ch not in self.c_table:
                return (0, 0)
            base = self.c_table[ch]
            lo = base + self._rank(ch, lo)
            hi = base + self._rank(ch, hi)
            if lo >= hi:
                return (lo, hi)
        return (lo, hi)

    def _locate_row(self, row: int) -> int:
        """Walk LF from ``row`` to a sampled suffix and return its text position."""
        steps = 0
        r = row
        while r not in self._sa_samples:
            c = self._char_at(r)
            r = self.c_table[c] + self._rank(c, r)
            steps += 1
        return (self._sa_samples[r] + steps) % self.length

    def verify(self) -> None:
        """Re-verify the index against the content hash it was built from.

        Reconstructs the indexed text from the BWT by walking the LF-mapping and
        re-hashes it, so a cached index whose ``bwt.bin``/tables were corrupted or
        tampered with on disk fails closed rather than serving wrong locations. An
        ``O(n)`` on-demand check — not run on every load.

        Raises:
            FMIndexIntegrityError: If the reconstructed text does not match the
                ``content_hash`` recorded at build time.
        """
        n = self.length
        chars = [""] * n
        row = 0  # the sorted rotation beginning with the sentinel
        for k in range(n):
            c = self._char_at(row)
            chars[n - 1 - k] = c
            row = self.c_table[c] + self._rank(c, row)
        text = "".join(chars).replace(_SENTINEL, "")
        actual = hashlib.sha256(text.encode()).hexdigest()
        if actual != self.content_hash:
            raise FMIndexIntegrityError(
                f"FM-index failed integrity check (expected {self.content_hash[:12]}…, "
                f"reconstructed {actual[:12]}…); the cached index is corrupt"
            )

    # -- queries ------------------------------------------------------------

    def count(self, pattern: str | DNASequence) -> int:
        """Return how many times ``pattern`` occurs in the indexed text."""
        p = str(pattern).upper()
        if not p:
            return 0
        lo, hi = self._bw_search(p)
        return hi - lo

    def locate(self, pattern: str | DNASequence) -> list[int]:
        """Return the sorted 0-based start positions of ``pattern`` occurrences."""
        p = str(pattern).upper()
        if not p:
            return []
        lo, hi = self._bw_search(p)
        return sorted(self._locate_row(r) for r in range(lo, hi))

    def pam_sites(self, pam: PAM, spacer_length: int) -> list[PamHit]:
        """Return PAM-anchored protospacer placements on the indexed strand.

        Each concrete instantiation of the (possibly degenerate) ``pam`` pattern
        is located; for every PAM occurrence with room for a full upstream
        protospacer, a :class:`PamHit` is emitted. Results are sorted by
        protospacer start. Minus-strand search is performed by indexing the
        reverse complement of the reference (a Phase 5 concern).

        Args:
            pam: The PAM pattern (e.g. ``NGG``).
            spacer_length: Protospacer length immediately 5' of the PAM.
        """
        pam_len = len(pam.pattern)
        hits: list[PamHit] = []
        for concrete in _expand_pam(pam):
            for pam_start in self.locate(concrete):
                proto_start = pam_start - spacer_length
                if proto_start < 0:
                    continue
                hits.append(
                    PamHit(
                        protospacer_start=proto_start,
                        pam_start=pam_start,
                        pam_end=pam_start + pam_len,
                        pam_sequence=concrete,
                    )
                )
        hits.sort(key=lambda h: (h.protospacer_start, h.pam_sequence))
        return hits

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Release the memory map, if any."""
        if self._mm is not None:
            self._mm.close()
            self._mm = None

    def __enter__(self) -> FMIndex:
        """Enter a context manager that releases the memory map on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Release the memory map on context exit."""
        self.close()


class GenomeIndex:
    """A persistent, memory-mapped, per-contig FM-index over a reference genome.

    Where :class:`FMIndex` indexes one sequence, ``GenomeIndex`` builds and holds
    one content-addressed FM-index per contig **for both strands** (plus and
    reverse-complement), so PAM-anchored candidate search over a whole genome:

    * **survives across runs** — each contig index is keyed by its content hash on
      disk, so a second run (or a fresh process) memory-maps the existing index
      instead of rebuilding it;
    * **does not pin the index in RAM** — the BWT is memory-mapped by default
      (pass ``in_memory=True`` to load eagerly), so a multi-gigabyte genome index
      is paged in on demand.

    The expensive suffix-array construction is the **native SA-IS kernel** when the
    crate is built (linear time); the query path is the memory-mapped pure-Python
    :class:`FMIndex`. This is the genome-scale reference backend the off-target
    engine consumes via ``search(..., genome_index=...)``.
    """

    def __init__(
        self,
        *,
        plus: dict[str, FMIndex],
        minus: dict[str, FMIndex],
        build: str | None,
    ) -> None:
        """Hold the per-contig plus/minus indexes (see :meth:`build_genome`)."""
        self._plus = plus
        self._minus = minus
        self.build = build

    @classmethod
    def build_genome(
        cls,
        reference: ReferenceGenome,
        *,
        contigs: list[str] | None = None,
        cache_dir: str | Path | None = None,
        in_memory: bool = False,
    ) -> GenomeIndex:
        """Build (or load from cache) a per-contig FM-index over ``reference``.

        Args:
            reference: The reference genome to index.
            contigs: Restrict to these contigs; defaults to every contig.
            cache_dir: Override for the index cache root.
            in_memory: Load each BWT into RAM instead of memory-mapping it.

        Returns:
            A ready-to-query :class:`GenomeIndex`.
        """
        names = list(contigs) if contigs is not None else list(reference.contigs)
        plus: dict[str, FMIndex] = {}
        minus: dict[str, FMIndex] = {}
        for chrom in names:
            seq = str(
                reference.fetch(
                    GenomicInterval(
                        chrom=chrom,
                        start=0,
                        end=reference.contig_length(chrom),
                        strand=Strand.PLUS,
                        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
                    )
                )
            )
            rc = str(DNASequence(seq).reverse_complement())
            # prefer_native=False forces the on-disk + memory-mapped path; the
            # native SA-IS kernel still accelerates the build inside _build_to_disk.
            plus[chrom] = FMIndex.build(
                seq, cache_dir=cache_dir, in_memory=in_memory, prefer_native=False
            )
            minus[chrom] = FMIndex.build(
                rc, cache_dir=cache_dir, in_memory=in_memory, prefer_native=False
            )
        return cls(plus=plus, minus=minus, build=reference.build)

    @property
    def contigs(self) -> tuple[str, ...]:
        """Return the indexed contig names."""
        return tuple(self._plus)

    def plus(self, contig: str) -> FMIndex:
        """Return the plus-strand index for ``contig``."""
        return self._plus[contig]

    def minus(self, contig: str) -> FMIndex:
        """Return the reverse-complement (minus-strand) index for ``contig``."""
        return self._minus[contig]

    def locate(self, contig: str, pattern: str | DNASequence) -> list[int]:
        """Return the sorted plus-strand start positions of ``pattern`` on ``contig``."""
        return self._plus[contig].locate(pattern)

    def pam_sites(self, contig: str, pam: PAM, spacer_length: int) -> list[PamHit]:
        """Return PAM-anchored protospacer placements on ``contig``'s plus strand."""
        return self._plus[contig].pam_sites(pam, spacer_length)

    def close(self) -> None:
        """Release every contig's memory map."""
        for fm in (*self._plus.values(), *self._minus.values()):
            fm.close()

    def __enter__(self) -> GenomeIndex:
        """Enter a context manager that releases all memory maps on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Release all memory maps on context exit."""
        self.close()
