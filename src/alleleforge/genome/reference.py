"""Reference-genome access: random sequence retrieval over a FASTA.

:class:`ReferenceGenome` wraps :mod:`pyfaidx` for fast random access and exposes
a single, careful :meth:`ReferenceGenome.fetch` that is **strand-aware**,
**bounds-checked**, and **N-pads contig ends** (flagging the result) rather than
crashing on an over-run. A registry of built-in builds (hg38, T2T-CHM13 v2,
mm39) supports *lazy*, checksum-verified, consent-gated download into the cache;
AlleleForge never auto-downloads a reference without the caller's explicit
``consent=True``, and refuses to fetch an artifact it cannot checksum-verify.

All coordinates here are **0-based half-open** (see
:class:`alleleforge.types.sequence.GenomicInterval`); 1-based intervals are
rejected because internal genome access must never run on I/O-boundary
coordinates.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pyfaidx import Fasta

from alleleforge.config import get_settings
from alleleforge.types.provenance import DatasetVersion
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand

if TYPE_CHECKING:
    from types import TracebackType

#: A downloader writes the artifact at ``url`` to ``dest``. Injected so tests
#: never touch the network; the default implementation is consent-gated.
Downloader = Callable[[str, Path], None]


class ConsentError(RuntimeError):
    """Raised when a download is needed but the caller withheld consent."""


class ChecksumError(RuntimeError):
    """Raised when a downloaded artifact fails checksum verification."""


@dataclass(frozen=True)
class BuildDescriptor:
    """A built-in reference build: where it comes from and how to verify it.

    Attributes:
        name: Build identifier (e.g. ``"hg38"``).
        version: Pinned assembly version (e.g. ``"GRCh38.p14"``).
        source_url: Canonical download URL for the FASTA.
        citation: Literature / assembly citation.
        sha256: Expected content hash; ``None`` means the build cannot be
            auto-downloaded (we refuse to fetch what we cannot verify).
        redistributable: Whether AlleleForge may vendor this build.
    """

    name: str
    version: str
    source_url: str
    citation: str
    sha256: str | None = None
    redistributable: bool = False

    def dataset_version(self) -> DatasetVersion:
        """Return the :class:`DatasetVersion` recorded in result provenance."""
        return DatasetVersion(
            name=self.name,
            version=self.version,
            source_url=self.source_url,
            sha256=self.sha256,
            citation=self.citation,
            redistributable=self.redistributable,
        )


#: Built-in builds. hg38 is the baseline; T2T-CHM13 v2 is auto-recommended for
#: hg38-ambiguous loci (see :mod:`alleleforge.genome.coordinates`); mm39 ships
#: for mouse. The real-genome ``sha256`` values are populated by the Phase 3
#: data registry; until then these builds cannot be auto-downloaded (a fetch
#: without a verifiable checksum is refused).
BUILTIN_BUILDS: dict[str, BuildDescriptor] = {
    "hg38": BuildDescriptor(
        name="hg38",
        version="GRCh38.p14",
        source_url="https://ftp.ensembl.org/pub/release-110/fasta/homo_sapiens/dna/"
        "Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz",
        citation="Schneider et al., Genome Res 2017 (GRCh38)",
        redistributable=False,
    ),
    "T2T-CHM13v2": BuildDescriptor(
        name="T2T-CHM13v2",
        version="v2.0",
        source_url="https://s3-us-west-2.amazonaws.com/human-pangenomics/T2T/CHM13/assemblies/"
        "analysis_set/chm13v2.0.fa.gz",
        citation="Nurk et al., Science 2022 (T2T-CHM13)",
        redistributable=False,
    ),
    "mm39": BuildDescriptor(
        name="mm39",
        version="GRCm39",
        source_url="https://ftp.ensembl.org/pub/release-110/fasta/mus_musculus/dna/"
        "Mus_musculus.GRCm39.dna.primary_assembly.fa.gz",
        citation="Church et al., PLoS Biol 2009 (GRCm39 lineage)",
        redistributable=False,
    ),
}


@dataclass(frozen=True)
class FetchResult:
    """The outcome of a :meth:`ReferenceGenome.fetch_result` call.

    Attributes:
        sequence: The retrieved sequence, reverse-complemented when the request
            is on the minus strand, with any contig-end padding applied.
        interval: The interval that was requested.
        left_pad: Bases of ``N`` padded before the contig start (always 0 for a
            valid 0-based interval; kept for symmetry).
        right_pad: Bases of ``N`` padded past the contig end.
    """

    sequence: DNASequence
    interval: GenomicInterval
    left_pad: int
    right_pad: int

    @property
    def padded(self) -> bool:
        """Return ``True`` if any ``N`` padding was applied (an over-run)."""
        return self.left_pad > 0 or self.right_pad > 0


def _verify_sha256(path: Path, expected: str) -> str:
    """Hash ``path`` and raise :class:`ChecksumError` on mismatch.

    Returns:
        The verified hex digest.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    if digest != expected:
        raise ChecksumError(f"checksum mismatch for {path}: got {digest}, expected {expected}")
    return digest


def _default_downloader(url: str, dest: Path) -> None:  # pragma: no cover - network
    """Fetch ``url`` to ``dest`` over the network (never exercised in CI)."""
    import urllib.request

    urllib.request.urlretrieve(url, dest)  # noqa: S310 - URLs come from the trusted registry


class ReferenceGenome:
    """Strand-aware, bounds-checked random access to a reference FASTA.

    Construct directly from a local FASTA path, or via
    :meth:`from_build` to resolve a built-in build (downloading on consent).

    A single instance is **safe to share across threads**: the underlying
    ``pyfaidx`` handle keeps a shared file position (a seek+read is not atomic),
    so concurrent reads would otherwise return interleaved, wrong bytes. Each
    file read is guarded by a per-instance lock, so the web server (whose sync
    handlers run in a threadpool over one shared reference) and any other
    multi-threaded caller get correct sequence; the lock covers only the read,
    not the CPU-bound design/search work that follows it.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        build: str | None = None,
        dataset_version: DatasetVersion | None = None,
    ) -> None:
        """Open ``path`` for random access.

        Args:
            path: Path to a FASTA file (a ``.fai`` index is created if absent).
            build: Optional build identifier this FASTA represents.
            dataset_version: Optional provenance descriptor for the build.
        """
        self.path = Path(path)
        self.build = build
        self.dataset_version = dataset_version
        self._fasta = Fasta(str(self.path), sequence_always_upper=True, rebuild=False)
        self._lock = threading.Lock()  # pyfaidx Fasta is not thread-safe; serialize reads

    @classmethod
    def from_build(
        cls,
        build: str,
        *,
        cache_dir: str | Path | None = None,
        consent: bool = False,
        downloader: Downloader | None = None,
        descriptor: BuildDescriptor | None = None,
    ) -> ReferenceGenome:
        """Resolve a built-in build, downloading it on consent if not cached.

        Args:
            build: A key into :data:`BUILTIN_BUILDS` (ignored if ``descriptor``
                is given).
            cache_dir: Override for the reference cache root.
            consent: Must be ``True`` to permit any network download.
            downloader: Injected fetcher ``(url, dest) -> None``; defaults to a
                network download (only reached with ``consent=True``).
            descriptor: An explicit build descriptor (used in tests).

        Returns:
            An open :class:`ReferenceGenome`.

        Raises:
            KeyError: If ``build`` is unknown and no ``descriptor`` is given.
            ConsentError: If a download is required but ``consent`` is ``False``.
            ChecksumError: If the build has no expected checksum, or the
                downloaded artifact fails verification.
        """
        desc = descriptor or BUILTIN_BUILDS.get(build)
        if desc is None:
            raise KeyError(f"unknown build {build!r}; known: {sorted(BUILTIN_BUILDS)}")
        root = Path(cache_dir) if cache_dir is not None else get_settings().cache_dir / "reference"
        fasta_path = root / f"{desc.name}.{desc.version}.fa"
        if not fasta_path.exists():
            if not consent:
                raise ConsentError(
                    f"reference {desc.name!r} is not cached; pass consent=True to download "
                    f"from {desc.source_url}"
                )
            if desc.sha256 is None:
                raise ChecksumError(
                    f"reference {desc.name!r} has no expected checksum; refusing to download "
                    "an unverifiable artifact"
                )
            root.mkdir(parents=True, exist_ok=True)
            (downloader or _default_downloader)(desc.source_url, fasta_path)
            _verify_sha256(fasta_path, desc.sha256)
        return cls(fasta_path, build=desc.name, dataset_version=desc.dataset_version())

    @property
    def contigs(self) -> tuple[str, ...]:
        """Return the contig names available in this reference."""
        return tuple(self._fasta.keys())

    def contig_length(self, chrom: str) -> int:
        """Return the length of ``chrom`` in bases.

        Raises:
            KeyError: If ``chrom`` is not present in the reference.
        """
        if chrom not in self._fasta:
            raise KeyError(f"unknown contig {chrom!r}")
        return len(self._fasta[chrom])

    def fetch(self, interval: GenomicInterval) -> DNASequence:
        """Return the reference sequence over ``interval`` (strand-aware).

        Equivalent to ``fetch_result(interval).sequence``. Over-runs past a
        contig end are ``N``-padded rather than raising; use
        :meth:`fetch_result` when you need to know whether padding occurred.
        """
        return self.fetch_result(interval).sequence

    def fetch_result(self, interval: GenomicInterval) -> FetchResult:
        """Return the sequence over ``interval`` with padding flags.

        The minus strand is reverse-complemented. Coordinates outside the contig
        are filled with ``N`` and counted in ``left_pad`` / ``right_pad``.

        Raises:
            ValueError: If ``interval`` is not 0-based half-open.
            KeyError: If the contig is not in the reference.
        """
        if interval.coordinate_system is not CoordinateSystem.ZERO_BASED_HALF_OPEN:
            raise ValueError("fetch requires a 0-based half-open interval")
        if interval.chrom not in self._fasta:
            raise KeyError(f"unknown contig {interval.chrom!r}")

        start, end = interval.start, interval.end
        # The pyfaidx handle has a shared file position, so the read (seek+slice)
        # is not thread-safe; hold the per-instance lock for the read only.
        with self._lock:
            length = len(self._fasta[interval.chrom])
            real_lo = min(max(start, 0), length)
            real_hi = max(min(end, length), real_lo)
            core = str(self._fasta[interval.chrom][real_lo:real_hi]) if real_hi > real_lo else ""
        left_pad = max(0, -start)
        right_pad = (end - start) - (real_hi - real_lo) - left_pad
        plus = "N" * left_pad + core.upper() + "N" * right_pad

        seq = DNASequence(plus)
        if interval.strand is Strand.MINUS:
            seq = seq.reverse_complement()
        return FetchResult(sequence=seq, interval=interval, left_pad=left_pad, right_pad=right_pad)

    def close(self) -> None:
        """Close the underlying FASTA handle."""
        self._fasta.close()

    def __enter__(self) -> ReferenceGenome:
        """Enter a context manager that closes the FASTA on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the FASTA handle on context exit."""
        self.close()
