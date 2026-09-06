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
from alleleforge.types.sequence import GenomicInterval, canonical_contig

#: gnomAD v4.1 genetic-ancestry group labels.
GNOMAD_POPULATIONS = ("afr", "amr", "asj", "eas", "fin", "nfe", "sas")


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


class GnomadDB:
    """Indexed access to gnomAD per-population allele frequencies."""

    def __init__(self, records: Iterable[PopulationFrequency]) -> None:
        """Hold ``records`` grouped by contig for interval queries."""
        # Index by canonical contig so a query named in the other style ("chr1"
        # vs "1") still resolves — otherwise a reference-vs-gnomAD naming mismatch
        # silently returns no records and population off-target augmentation is
        # empty (the reference-bias blind spot this module exists to catch).
        self._by_chrom: dict[str, list[PopulationFrequency]] = {}
        for rec in records:
            self._by_chrom.setdefault(canonical_contig(rec.chrom), []).append(rec)
        for recs in self._by_chrom.values():
            recs.sort(key=lambda r: r.pos)

    @classmethod
    def from_sites_tsv(cls, path: str | Path) -> GnomadDB:
        """Parse a ``chrom pos ref alt af <pop>...`` TSV (plain or ``.gz``)."""
        return cls(cls._parse(path))

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
