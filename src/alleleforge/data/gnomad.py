"""gnomAD population allele-frequency access.

:class:`GnomadDB` answers :meth:`GnomadDB.frequencies` over a genomic interval,
returning per-population minor-allele frequencies used by the Phase 5 off-target
engine to find population variants that create *de novo* PAMs or alter seed-region
mismatches. The default release is **gnomAD v4.1** (see the Phase 3 registry).

Production reads tabix slices of the gnomAD sites VCF; the test path parses a
small plain-text TSV so CI needs no ``pysam`` and no multi-gigabyte file. The TSV
columns are ``chrom pos ref alt af <pop>...`` with ``pos`` **1-based** (matching
the gnomAD VCF), normalized to 0-based on read.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from alleleforge.config import get_settings
from alleleforge.data._io import is_sequence_allele, open_text
from alleleforge.types.provenance import DatasetVersion
from alleleforge.types.sequence import GenomicInterval, canonical_contig

#: gnomAD v4.1 genetic-ancestry group labels, as they appear in ``AF_<group>`` INFO keys.
#:
#: Corrected from a seven-element list that omitted ``ami`` (Amish), ``mid`` (Middle
#: Eastern) and ``remaining``. A real v4.1 row carries all ten, so a reader filtering on
#: the shorter list silently dropped two *named ancestries* — in the dataset that makes
#: this tool population-aware, which is the opposite of the point.
#:
#: Explicitly listed rather than matched as ``AF_*``, because the pattern is wrong in a
#: way that matters. The same row also carries ``AF_XX``/``AF_XY`` (sex strata), every
#: ancestry crossed with sex (``AF_nfe_XY``), ``AF_grpmax`` (a maximum *across* groups)
#: and ``AF_raw`` (pre-filter) — 34 ``AF_*`` keys in total. Admitting those would put
#: ``XX`` into :attr:`GnomadDB.available_populations`, which this project reads as "an
#: ancestry that was examined", making it a false claim about coverage. A group gnomAD
#: adds later is skipped until it is named here: a missing ancestry is visibly missing,
#: an invented one is not.
GNOMAD_POPULATIONS = (
    "afr",
    "ami",
    "amr",
    "asj",
    "eas",
    "fin",
    "mid",
    "nfe",
    "remaining",
    "sas",
)


class PopulationFrequency(BaseModel):
    """An allele's overall and per-population frequencies at one locus.

    Attributes:
        chrom: Contig name.
        pos: 0-based start coordinate of ``ref``.
        ref: Reference allele.
        alt: Alternate allele.
        overall_af: Overall allele frequency (``AF``).
        populations: Per-population allele frequency, keyed by ancestry label.
    """

    model_config = ConfigDict(frozen=True)

    chrom: str
    pos: int
    ref: str
    alt: str
    overall_af: float
    populations: dict[str, float] = {}

    @model_validator(mode="after")
    def _frequencies_are_fractions(self) -> PopulationFrequency:
        """Reject a frequency outside ``[0, 1]``.

        A frequency column given as a *percentage* (0-100) is the ordinary way this
        happens, and it was accepted silently: the MAF filter then admits everything,
        and the report shows an ancestry frequency of "200%". The numbers this carries
        are read by a human deciding whether a guide is safe in a population, so a
        scale error has to fail at the parse boundary rather than propagate — the
        alternative is a safety figure that is wrong by 100x and looks deliberate.
        """
        bad = {"overall_af": self.overall_af} | {
            pop: freq for pop, freq in self.populations.items() if not 0.0 <= freq <= 1.0
        }
        if 0.0 <= self.overall_af <= 1.0:
            del bad["overall_af"]
        if bad:
            listed = ", ".join(f"{k}={v!r}" for k, v in sorted(bad.items()))
            raise ValueError(
                f"allele frequency outside [0, 1] at {self.chrom}:{self.pos}: {listed}. "
                "Frequencies are fractions, not percentages — divide a percent column "
                "by 100."
            )
        return self

    def max_af(self, populations: Sequence[str] | None = None) -> float:
        """Return the highest frequency across the requested populations.

        Args:
            populations: Ancestry labels to consider; ``None`` considers every
                population plus the overall frequency.
        """
        if populations is None:
            return max([self.overall_af, *self.populations.values()], default=self.overall_af)
        return max((self.populations.get(p, 0.0) for p in populations), default=0.0)

    def exceeds(self, maf: float, populations: Sequence[str] | None = None) -> bool:
        """Return ``True`` if the allele meets ``maf`` in any queried population."""
        return self.max_af(populations) >= maf

    @property
    def variant_key(self) -> str:
        """Return a compact ``chrom:pos:ref>alt`` causal-allele key."""
        return f"{self.chrom}:{self.pos}:{self.ref}>{self.alt}"


#: The columns every sites row must carry; anything after them is an ancestry
#: label, and a row may omit those trailing values.
_CORE_COLUMNS = ("chrom", "pos", "ref", "alt", "af")


def _af_list(raw: str | None) -> list[str]:
    """Split a VCF ``Number=A`` frequency field, or return ``[]`` when absent."""
    return [] if raw in (None, "", ".") else str(raw).split(",")


def _per_allele(values: list[str], index: int) -> float | None:
    """Return ``values[index]`` as a float, or ``None`` when absent or unparseable.

    ``Number=A`` means one value per ALT, so a multi-allelic row's frequencies line up
    with its alleles by position. A single value with several ALTs, or a ``.`` placeholder,
    means this allele has no frequency — which is absence, not zero, and the record omits
    the group rather than claiming it was measured at 0.
    """
    if index >= len(values):
        return None
    try:
        return float(values[index])
    except ValueError:
        return None


class GnomadDB:
    """Indexed access to gnomAD per-population allele frequencies."""

    def __init__(self, records: Iterable[PopulationFrequency]) -> None:
        """Hold ``records`` grouped by contig for interval queries."""
        # Index by canonical contig so a query named in the other style ("chr1"
        # vs "1") still resolves — otherwise a reference-vs-gnomAD naming mismatch
        # silently returns no records and population off-target augmentation is
        # empty (the reference-bias blind spot this module exists to catch).
        #: The provenance descriptor pinning the bytes these records came from, set
        #: by whichever shell loaded them (see `HaplotypePanel.dataset_version`).
        self.dataset_version: DatasetVersion | None = None
        self._by_chrom: dict[str, list[PopulationFrequency]] = {}
        for rec in records:
            self._by_chrom.setdefault(canonical_contig(rec.chrom), []).append(rec)
        for recs in self._by_chrom.values():
            recs.sort(key=lambda r: r.pos)

    @classmethod
    def from_sites_tsv(cls, path: str | Path) -> GnomadDB:
        """Parse a ``chrom pos ref alt af <pop>...`` TSV (plain or ``.gz``)."""
        return cls(cls._parse(path))

    @classmethod
    def load(cls, path: str | Path) -> GnomadDB:
        """Read either form gnomAD data arrives in, deciding by content not by name.

        Sniffed for the same reason dbSNP's loader is: gnomAD's released files are named
        ``gnomad.genomes.v4.1.sites.chr22.vcf.bgz``, and a caller's own extract may be
        named anything. Dispatch is on the *positive* VCF signal — a first line of
        ``##fileformat=VCF`` — and everything else falls through to
        :meth:`from_sites_tsv`, whose header check already produces the column-by-column
        diagnosis a nearly-right file needs. Adding a second "neither format" error here
        would replace that better message with a worse one.
        """
        for line in open_text(path):
            if not line.strip():
                continue
            if line.startswith("##fileformat=VCF"):
                return cls.from_vcf(path)
            break
        return cls.from_sites_tsv(path)

    @classmethod
    def from_vcf(cls, path: str | Path) -> GnomadDB:
        """Parse a gnomAD sites VCF (plain, ``.gz`` or ``.bgz``) into a :class:`GnomadDB`.

        This is the artifact gnomAD actually publishes. Until now the only reader was
        :meth:`from_sites_tsv`, which wants a ``chrom pos ref alt af <pop>...`` table
        nothing in this project produces — so the input that makes a scan
        population-aware, the capability this tool is built around, required a conversion
        the caller had to write. The same gap as dbSNP's, in the dataset that matters
        most.

        Three things about gnomAD's INFO field that a reader has to get right, and the
        first is the dangerous one:

        * **Most ``AF_*`` keys are not ancestries.** A real v4.1 row carries 34 of them:
          ``AF_XX``/``AF_XY`` (sex strata), ``AF_<grp>_XX``/``_XY`` (ancestry x sex),
          ``AF_grpmax`` (a maximum across groups) and ``AF_raw`` (pre-filter) alongside
          the ten real ancestry groups. Taking every ``AF_*`` would make
          :attr:`available_populations` advertise ``XX`` as an ancestry a caller can
          stratify by — and this project reports which ancestries it *examined*, so that
          is a false claim about coverage rather than a cosmetic error. Only the ten
          named groups are read.
        * **A group's key is absent when it has no data** for that site, so the keys
          present vary row to row; the record carries what the row carries.
        * **A non-PASS ``FILTER`` is gnomAD's own verdict** that the call is unreliable
          (``AC0`` = no high-quality genotype, ``AS_VQSR`` = failed the site filter).
          Those rows are skipped: a frequency this tool puts in front of somebody should
          be one upstream stands behind.

        Returns:
            A queryable :class:`GnomadDB`.
        """
        return cls(cls._parse_vcf(path))

    @staticmethod
    def _parse_vcf(path: str | Path) -> Iterator[PopulationFrequency]:
        """Yield one :class:`PopulationFrequency` per usable (row, ALT) pair."""
        for line in open_text(path):
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 8:
                continue
            chrom, pos, _id, ref, alts, _qual, filt, info = cols[:8]
            if filt not in ("PASS", ".", ""):
                continue  # gnomAD's own quality verdict
            # `partition`, not `split("=", 1)`: a VCF INFO field may be a bare flag with
            # no value, and the mixed list/tuple that a conditional split produces is not
            # a mapping item — mypy caught it before a flag-only row could.
            fields: dict[str, str] = {}
            for entry in info.split(";"):
                if entry:
                    key, _, raw_value = entry.partition("=")
                    fields[key] = raw_value
            overall = _af_list(fields.get("AF"))
            if not overall:
                continue
            alt_list = alts.split(",")
            for index, alt in enumerate(alt_list):
                if not is_sequence_allele(ref, alt):
                    continue
                af = _per_allele(overall, index)
                if af is None:
                    continue
                pops = {
                    group: freq
                    for group in GNOMAD_POPULATIONS
                    if (freq := _per_allele(_af_list(fields.get(f"AF_{group}")), index)) is not None
                }
                yield PopulationFrequency(
                    chrom=chrom,
                    pos=int(pos) - 1,  # VCF is 1-based; store 0-based
                    ref=ref,
                    alt=alt,
                    overall_af=af,
                    populations=pops,
                )

    @staticmethod
    def _parse(path: str | Path) -> Iterator[PopulationFrequency]:
        """Yield one :class:`PopulationFrequency` per TSV data row.

        A malformed file is refused with the line and what was wrong. This is the
        input that makes a scan population-aware, and it was the one user-supplied
        format whose parse errors escaped as a bare ``KeyError`` from the row dict:
        ``zip(..., strict=False)`` truncates silently, so a short row lost the keys
        the parser then indexed.

        A row that omits only *trailing population* columns stays legal — a ragged
        tail is ordinary in a hand-assembled panel and an absent per-population value
        is already treated as absent. What is refused is a row that cannot supply the
        core columns, a row carrying an unnamed extra column (data ``zip`` would have
        dropped), and a header naming the same column twice, which has no single
        meaning.

        Raises:
            ValueError: On a missing header, a missing core column, a duplicated
                column name, or a row whose field count cannot be reconciled.
        """
        header: list[str] | None = None
        for lineno, line in enumerate(open_text(path), start=1):
            if not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if line.startswith("#"):
                header = [c.lstrip("#") for c in cols]
                duplicates = sorted({c for c in header if header.count(c) > 1})
                if duplicates:
                    raise ValueError(
                        f"gnomAD TSV header names the same column twice: "
                        f"{', '.join(duplicates)} (line {lineno}). Two frequencies for "
                        "one ancestry have no single meaning; remove one."
                    )
                missing = [c for c in _CORE_COLUMNS if c not in header]
                if missing:
                    raise ValueError(
                        f"gnomAD TSV header is missing {', '.join(missing)} (line "
                        f"{lineno}). Expected a tab-separated header of: "
                        f"{'  '.join(_CORE_COLUMNS)}  <pop>..."
                    )
                continue
            if header is None:
                raise ValueError("gnomAD TSV is missing its '#chrom ...' header line")
            if len(cols) < len(_CORE_COLUMNS) or len(cols) > len(header):
                raise ValueError(
                    f"gnomAD TSV line {lineno} has {len(cols)} field(s); expected "
                    f"between {len(_CORE_COLUMNS)} and {len(header)} for the header "
                    f"{'  '.join(header)}"
                )
            row = dict(zip(header, cols, strict=False))
            # A symbolic/spanning-deletion ALT (`*`, `<DEL>`) is not literal sequence;
            # skip it instead of storing a bogus PopulationFrequency (clinvar/dbsnp skip
            # it too — the three loaders agree on what a usable row is).
            if not is_sequence_allele(row["ref"], row["alt"]):
                continue
            pops = {p: float(row[p]) for p in header[5:] if row.get(p) not in (None, "", ".")}
            yield PopulationFrequency(
                chrom=row["chrom"],
                pos=int(row["pos"]) - 1,  # gnomAD VCF is 1-based; store 0-based
                ref=row["ref"],
                alt=row["alt"],
                overall_af=float(row["af"]),
                populations=pops,
            )

    @cached_property
    def available_populations(self) -> frozenset[str]:
        """Return every ancestry label any record in this source carries.

        Needed to tell a *requested* population apart from a *backed* one. Asking for
        an ancestry the source has no column for silently contributes nothing, while
        provenance records it among the populations considered — so the report asserts
        an ancestry was examined when no data for it exists.

        Cached: this is a full scan of the database, and ``search()`` asks for it once
        per call — which is once per *candidate* in a design. Measured over 200,000
        records it costs 49 ms, so a 470-candidate prime menu paid 23 seconds for a
        label, and a real per-chromosome gnomAD file is an order of magnitude larger.
        The database is immutable once constructed, so one computation is enough.
        """
        return frozenset(
            pop for recs in self._by_chrom.values() for rec in recs for pop in rec.populations
        )

    def frequencies(
        self,
        interval: GenomicInterval,
        *,
        populations: Sequence[str] | None = None,
        maf: float | None = None,
    ) -> list[PopulationFrequency]:
        """Return allele frequencies overlapping ``interval``.

        Args:
            interval: The query window (0-based half-open).
            populations: Restrict each record's ``populations`` dict to these
                labels; ``None`` keeps every population.
            maf: If given, drop records that do not reach ``maf`` in any queried
                population (the Phase 5 inclusion threshold, default 0.001).

        Returns:
            Matching records, sorted by position.
        """
        out: list[PopulationFrequency] = []
        for rec in self._by_chrom.get(canonical_contig(interval.chrom), ()):
            if not interval.start <= rec.pos < interval.end:
                continue
            if populations is not None:
                rec = rec.model_copy(
                    update={"populations": {p: rec.populations.get(p, 0.0) for p in populations}}
                )
            if maf is not None and not rec.exceeds(maf, populations):
                continue
            out.append(rec)
        return out


def load_default(
    *,
    cache_dir: str | Path | None = None,
    consent: bool = False,
) -> GnomadDB:  # pragma: no cover - requires the fetched release
    """Load the registry-pinned gnomAD release from the user cache.

    Fetches on ``consent=True`` via the default registry; raises otherwise. Not
    exercised in CI, which uses small synthetic TSV fixtures instead.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY

    root = Path(cache_dir) if cache_dir is not None else get_settings().cache_dir / "data"
    path, _ = DEFAULT_REGISTRY.resolve("gnomad", cache_dir=root, consent=consent)
    return GnomadDB.from_sites_tsv(path)
