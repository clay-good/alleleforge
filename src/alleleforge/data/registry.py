"""License-aware, versioned dataset registry with consent-gated fetching.

Every external dataset AlleleForge touches (ClinVar, gnomAD, 1000 Genomes, HGDP,
dbSNP, GENCODE, ENCODE) is declared here as a typed :class:`DatasetDescriptor`
recording its ``source_url``, ``license``, ``citation``, ``version``, ``sha256``,
and a ``redistributable`` flag. The registry is the single choke point for data
acquisition, and it enforces two invariants from the specification:

* **No non-redistributable dataset is ever vendored.** A descriptor with
  ``redistributable=False`` is only ever fetched into the *user's* cache at
  runtime, with explicit ``consent=True``; it is never written into the repo or
  a built image.
* **No unverifiable artifact is fetched.** A download requires a pinned
  ``sha256``; AlleleForge refuses to fetch what it cannot checksum-verify, and
  raises if the downloaded bytes do not match.

Access returns the cached path together with a :class:`DatasetVersion` for the
result provenance block, so any analysis can be traced back to the exact dataset
release it used.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

from alleleforge.config import get_settings
from alleleforge.types.provenance import DatasetVersion

#: A downloader writes the artifact at ``url`` to ``dest``. Injected so tests
#: never touch the network; the default implementation is consent-gated.
Downloader = Callable[[str, Path], None]


class ConsentError(RuntimeError):
    """Raised when a fetch is needed but the caller withheld consent."""


class ChecksumError(RuntimeError):
    """Raised when an artifact is unverifiable or fails checksum verification."""


class DatasetDescriptor(DatasetVersion):
    """A registry entry: a :class:`DatasetVersion` plus how to cache it.

    Extends the provenance-facing :class:`DatasetVersion` with the local cache
    ``filename`` and an optional ``populations`` annotation for the
    ancestry-stratified sources (gnomAD, 1000G, HGDP).

    Attributes:
        filename: The basename the artifact is cached under.
        populations: Population/ancestry labels this dataset stratifies by.
    """

    filename: str
    populations: tuple[str, ...] = ()

    def dataset_version(self) -> DatasetVersion:
        """Return the plain :class:`DatasetVersion` recorded in provenance."""
        return DatasetVersion(
            name=self.name,
            version=self.version,
            source_url=self.source_url,
            license=self.license,
            sha256=self.sha256,
            citation=self.citation,
            redistributable=self.redistributable,
        )


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


class DatasetRegistry:
    """A keyed collection of :class:`DatasetDescriptor` with cached resolution."""

    def __init__(self, descriptors: dict[str, DatasetDescriptor] | None = None) -> None:
        """Initialise the registry, optionally seeding it with descriptors."""
        self._descriptors: dict[str, DatasetDescriptor] = dict(descriptors or {})

    def register(self, descriptor: DatasetDescriptor) -> None:
        """Add or replace a descriptor keyed by its ``name``."""
        self._descriptors[descriptor.name] = descriptor

    def __contains__(self, name: str) -> bool:
        """Return ``True`` if a descriptor named ``name`` is registered."""
        return name in self._descriptors

    @property
    def names(self) -> tuple[str, ...]:
        """Return the registered dataset names, sorted."""
        return tuple(sorted(self._descriptors))

    def get(self, name: str) -> DatasetDescriptor:
        """Return the descriptor named ``name``.

        Raises:
            KeyError: If no dataset by that name is registered.
        """
        if name not in self._descriptors:
            raise KeyError(f"unknown dataset {name!r}; known: {self.names}")
        return self._descriptors[name]

    def cache_path(self, name: str, *, cache_dir: str | Path | None = None) -> Path:
        """Return the on-disk cache path an artifact resolves to (if present)."""
        desc = self.get(name)
        root = Path(cache_dir) if cache_dir is not None else get_settings().cache_dir / "data"
        return root / desc.name / desc.filename

    def resolve(
        self,
        name: str,
        *,
        cache_dir: str | Path | None = None,
        consent: bool = False,
        downloader: Downloader | None = None,
    ) -> tuple[Path, DatasetVersion]:
        """Return the cached artifact path and its :class:`DatasetVersion`.

        If the artifact is not cached, a download is attempted only when
        ``consent=True`` and the descriptor carries a pinned ``sha256``; the
        downloaded bytes are then checksum-verified. A non-redistributable
        dataset is fetched into the user's cache exactly like any other — it is
        simply never vendored into the repository or an image.

        Args:
            name: The registered dataset name.
            cache_dir: Override for the data cache root.
            consent: Must be ``True`` to permit any network download.
            downloader: Injected fetcher ``(url, dest) -> None``; defaults to a
                network download (only reached with ``consent=True``).

        Returns:
            ``(path, dataset_version)``.

        Raises:
            KeyError: If ``name`` is not registered.
            ConsentError: If a fetch is required but ``consent`` is ``False``.
            ChecksumError: If the descriptor has no pinned checksum, or the
                downloaded artifact fails verification.
        """
        desc = self.get(name)
        path = self.cache_path(name, cache_dir=cache_dir)
        if not path.exists():
            if not consent:
                raise ConsentError(
                    f"dataset {desc.name!r} is not cached; pass consent=True to download "
                    f"from {desc.source_url}"
                )
            if desc.sha256 is None:
                raise ChecksumError(
                    f"dataset {desc.name!r} has no pinned checksum; refusing to download "
                    "an unverifiable artifact"
                )
            if desc.source_url is None:
                raise ConsentError(f"dataset {desc.name!r} has no source_url to download from")
            path.parent.mkdir(parents=True, exist_ok=True)
            (downloader or _default_downloader)(desc.source_url, path)
            _verify_sha256(path, desc.sha256)
        elif desc.sha256 is not None:
            # Hash-on-read: re-verify a cached dataset against its pinned checksum
            # on every resolve, so a tampered cache entry is rejected on load.
            _verify_sha256(path, desc.sha256)
        return path, desc.dataset_version()


#: The default registry, pinning every Phase 3 dataset to a release with its
#: license and citation. ``sha256`` is intentionally ``None`` until the data
#: layer pins concrete release artifacts; that keeps auto-download disabled (a
#: fetch without a verifiable checksum is refused) while the descriptors already
#: document provenance for ``docs/data.md`` and the ``aforge data`` command.
DEFAULT_REGISTRY = DatasetRegistry(
    {
        "clinvar": DatasetDescriptor(
            name="clinvar",
            version="2024-05",
            source_url="https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz",
            license="public-domain (NCBI)",
            citation="Landrum et al., Nucleic Acids Res 2018 (ClinVar)",
            redistributable=True,
            filename="clinvar.vcf.gz",
        ),
        "gnomad": DatasetDescriptor(
            name="gnomad",
            version="v4.1",
            source_url="https://gnomad.broadinstitute.org/downloads",
            license="CC0-1.0",
            citation="Chen et al., Nature 2024 (gnomAD v4)",
            redistributable=True,
            filename="gnomad.v4.1.sites.tsv.gz",
            populations=("afr", "amr", "asj", "eas", "fin", "nfe", "sas"),
        ),
        "1000g": DatasetDescriptor(
            name="1000g",
            version="phase3-highcov",
            source_url="https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/"
            "1000G_2504_high_coverage/",
            license="public (IGSR / 1000 Genomes)",
            citation="Byrska-Bishop et al., Cell 2022 (1000G high-coverage)",
            redistributable=True,
            filename="1000g.phase3.haplotypes.tsv.gz",
            populations=("AFR", "AMR", "EAS", "EUR", "SAS"),
        ),
        "hgdp": DatasetDescriptor(
            name="hgdp",
            version="gnomad-v3.1",
            source_url="https://gnomad.broadinstitute.org/downloads#v3-hgdp-1kg",
            license="CC0-1.0",
            citation="Bergstrom et al., Science 2020 (HGDP)",
            redistributable=True,
            filename="hgdp.haplotypes.tsv.gz",
            populations=(
                "africa",
                "america",
                "central_south_asia",
                "east_asia",
                "europe",
                "middle_east",
                "oceania",
            ),
        ),
        "dbsnp": DatasetDescriptor(
            name="dbsnp",
            version="b156",
            source_url="https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz",
            license="public-domain (NCBI)",
            citation="Sherry et al., Nucleic Acids Res 2001 (dbSNP)",
            redistributable=True,
            filename="dbsnp.b156.tsv.gz",
        ),
        "gencode": DatasetDescriptor(
            name="gencode",
            version="v47",
            source_url="https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_47/"
            "gencode.v47.annotation.gtf.gz",
            license="custom (GENCODE / open)",
            citation="Frankish et al., Nucleic Acids Res 2023 (GENCODE)",
            redistributable=True,
            filename="gencode.v47.annotation.gtf.gz",
        ),
        "encode": DatasetDescriptor(
            name="encode",
            version="2024",
            source_url="https://www.encodeproject.org/",
            license="open (ENCODE data-use policy)",
            citation="ENCODE Project Consortium, Nature 2012",
            redistributable=True,
            filename="encode.tracks.bedgraph.gz",
        ),
        # The Doench 2016 CFD off-target weight matrix. Unlike the sources above, this
        # one is vendored into the package (offtarget/cfd_matrix.json) and so carries a
        # real pinned sha256 of the shipped file — the 240 mismatch weights are
        # byte-identical across two independent tools (CRISPOR, CRISPRitz); see the
        # file's own `_provenance` block for the cross-verification record.
        "doench-2016-cfd": DatasetDescriptor(
            name="doench-2016-cfd",
            version="2016",
            source_url=(
                "https://raw.githubusercontent.com/maximilianh/crisporWebsite/master/"
                "CFD_Scoring/mismatch_score.pkl"
            ),
            license="published data (Doench et al. 2016); redistributed via CRISPOR/CRISPRitz",
            citation="Doench et al., Nat Biotechnol 2016 (CFD; Suppl. Table 19)",
            sha256="9134bbd7609507beef37fcc3a046a56a0ab2ed78d8456ea751528e6993451496",
            redistributable=True,
            filename="cfd_matrix.json",
        ),
    }
)
