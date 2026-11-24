"""Phased-haplotype panels shared by the 1000 Genomes and HGDP sources.

A :class:`HaplotypePanel` enumerates the **common haplotypes** spanning a query
interval, each carried at some per-population frequency. The Phase 5 off-target
engine walks these haplotypes (in the Rust ``haplotype.rs`` kernel) so that an
off-target created only on a common non-reference haplotype is still nominated,
and is reported with the populations that carry it.

Two readers, and until R703 only the second existed — while this sentence already
claimed the first. :meth:`HaplotypePanel.from_phased_vcf` builds a panel from the phased
VCFs that 1000G and HGDP actually publish, over a caller-chosen window and with a
sample-to-population mapping (:func:`read_sample_populations` reads the one 1000G
publishes beside them). :meth:`HaplotypePanel.from_tsv` parses a small plain-text panel,
which is what the tests use and what a hand-assembled panel looks like. Each TSV row is
one ``(haplotype, population)`` observation:

``hap_id  chrom  start  end  population  frequency  variants``

where ``start``/``end`` are 0-based half-open, ``variants`` is a comma-separated
list of ``chrom:pos:ref>alt`` (0-based ``pos``) or empty for the reference
haplotype.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.data._io import open_text
from alleleforge.types.provenance import DatasetVersion
from alleleforge.types.sequence import GenomicInterval, Strand, canonical_contig
from alleleforge.types.variant import Variant


def read_sample_populations(path: str | Path, *, column: str = "Superpopulation") -> dict[str, str]:
    """Read 1000G's sample-to-population table into a mapping.

    1000G publishes this beside the phased VCFs as
    ``20130606_g1k_3202_samples_ped_population.txt``, and it is **space**-separated with
    the columns ``FamilyID SampleID FatherID MotherID Sex Population Superpopulation``.
    Three things about it are easy to get wrong and all three change the answer:

    * it is not a TSV, so splitting on tabs yields one column;
    * ``SampleID`` is the second field, not the first — the first is the family;
    * there are **two** population columns, and they are different questions.
      ``Population`` is the cohort (``GBR``, ``YRI``); ``Superpopulation`` is the
      continental group (``EUR``, ``AFR``). The dataset registry describes ``1000g``
      with the five superpopulations, so that is the default — a panel keyed by cohort
      would advertise ancestries no descriptor mentions and would not match a
      ``--populations EUR`` request.

    Args:
        path: The published population table.
        column: Which population column to key frequencies by.

    Returns:
        Sample ID -> population label.

    Raises:
        ValueError: If the header does not name ``SampleID`` and ``column``.
    """
    mapping: dict[str, str] = {}
    header: list[str] | None = None
    for line in open_text(path):
        fields = line.split()
        if not fields:
            continue
        if header is None:
            header = fields
            for needed in ("SampleID", column):
                if needed not in header:
                    raise ValueError(
                        f"{path} does not name a {needed!r} column; found "
                        f"{'  '.join(header)}. Expected 1000G's "
                        "'FamilyID SampleID FatherID MotherID Sex Population "
                        "Superpopulation' table."
                    )
            continue
        if len(fields) < len(header):
            continue
        row = dict(zip(header, fields, strict=False))
        mapping[row["SampleID"]] = row[column]
    if header is None:
        raise ValueError(f"{path} is empty")
    return mapping


class Haplotype(BaseModel):
    """A common haplotype over a window and the populations carrying it.

    Attributes:
        hap_id: Panel-local haplotype identifier.
        interval: The window the haplotype is defined over (0-based half-open).
        variants: The non-reference alleles the haplotype carries, in order.
        frequencies: Per-population frequency of the haplotype.
        source: The panel that produced it (e.g. ``"1000g"``, ``"hgdp"``).
    """

    model_config = ConfigDict(frozen=True)

    hap_id: str
    interval: GenomicInterval
    variants: tuple[Variant, ...]
    frequencies: dict[str, float]
    source: str

    @property
    def is_reference(self) -> bool:
        """Return ``True`` if the haplotype carries no non-reference allele."""
        return len(self.variants) == 0

    @property
    def populations(self) -> tuple[str, ...]:
        """Return the populations that carry this haplotype (frequency > 0)."""
        return tuple(sorted(p for p, f in self.frequencies.items() if f > 0.0))

    def max_freq(self, populations: Sequence[str] | None = None) -> float:
        """Return the highest frequency over the requested populations."""
        if populations is None:
            return max(self.frequencies.values(), default=0.0)
        return max((self.frequencies.get(p, 0.0) for p in populations), default=0.0)


def _parse_variants(field: str) -> tuple[Variant, ...]:
    """Parse a ``chrom:pos:ref>alt,...`` field (0-based pos) into variants."""
    field = field.strip()
    if not field or field == ".":
        return ()
    variants: list[Variant] = []
    for token in field.split(","):
        chrom, pos_s, alleles = token.split(":")
        ref, alt = alleles.split(">")
        variants.append(Variant(chrom=chrom, pos=int(pos_s), ref=ref, alt=alt).normalized())
    return tuple(variants)


class HaplotypePanel:
    """A queryable panel of common phased haplotypes."""

    def __init__(self, haplotypes: Iterable[Haplotype], *, source: str) -> None:
        """Hold ``haplotypes`` grouped by contig; record the panel ``source``."""
        self.source = source
        #: The provenance descriptor pinning the bytes this panel was read from, set by
        #: whichever shell loaded it. Declared here rather than attached from outside:
        #: `_collect_datasets` reads it off this object, and when only one shell knew to
        #: attach it the other recorded nothing about the panel that made a run
        #: haplotype-aware.
        self.dataset_version: DatasetVersion | None = None
        # Index by canonical contig so a query named in the other style ("chr1"
        # vs "1") still resolves — a panel built from a bare-named 1000G/HGDP VCF
        # queried with a chr-named hg38 interval would otherwise miss its bucket
        # and silently return no haplotypes, yielding an empty haplotype-aware
        # off-target pass (the reference-bias blind spot this module exists to
        # catch). `overlaps` is already naming-aware, but the bucket lookup below
        # runs first and never reached it.
        self._by_chrom: dict[str, list[Haplotype]] = defaultdict(list)
        for hap in haplotypes:
            self._by_chrom[canonical_contig(hap.interval.chrom)].append(hap)

    @classmethod
    def from_tsv(cls, path: str | Path, *, source: str) -> HaplotypePanel:
        """Parse a phased-haplotype TSV (plain or ``.gz``) into a panel.

        Each ``(haplotype, population)`` row contributes one frequency; rows
        sharing a ``hap_id`` and span are merged into a single haplotype whose
        per-population frequencies are accumulated in encounter order.
        """
        intervals: dict[tuple[str, str], GenomicInterval] = {}
        variants: dict[tuple[str, str], tuple[Variant, ...]] = {}
        freqs: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        header: list[str] | None = None
        for line in open_text(path):
            if not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if line.startswith("#"):
                header = [c.lstrip("#") for c in cols]
                continue
            if header is None:
                raise ValueError("haplotype TSV is missing its '#hap_id ...' header line")
            row = dict(zip(header, cols, strict=False))
            start, end = int(row["start"]), int(row["end"])
            key = (row["hap_id"], f"{row['chrom']}:{start}-{end}")
            if key not in intervals:
                intervals[key] = GenomicInterval(
                    chrom=row["chrom"], start=start, end=end, strand=Strand.PLUS
                )
                variants[key] = _parse_variants(row.get("variants", ""))
            freqs[key][row["population"]] = float(row["frequency"])
        haplotypes = [
            Haplotype(
                hap_id=key[0],
                interval=intervals[key],
                variants=variants[key],
                frequencies=freqs[key],
                source=source,
            )
            for key in intervals
        ]
        return cls(haplotypes, source=source)

    @classmethod
    def from_phased_vcf(
        cls,
        path: str | Path,
        *,
        interval: GenomicInterval,
        sample_populations: Mapping[str, str],
        source: str,
    ) -> HaplotypePanel:
        """Build a panel from a phased VCF — the path this module said it already had.

        This module's own docstring opened with "Production builds these from phased
        VCFs; the test path parses a small plain-text TSV". Only the test path existed.
        `from_tsv` was the sole reader, so the sentence described a pipeline no caller
        could run, and 1000G and HGDP — which publish exactly these phased VCFs — were
        usable only after the caller wrote the conversion themselves.

        A haplotype is defined *over a window*, so ``interval`` is required rather than
        inferred: "the haplotypes of chromosome 22" is not a thing, and a reader that
        silently chose a span would decide the question the caller is asking.

        Frequencies are per population and need a sample-to-population mapping, which
        1000G publishes beside the VCFs (``20130606_g1k_3202_samples_ped_population.txt``);
        :func:`read_sample_populations` reads it. Samples absent from the mapping are
        skipped entirely rather than pooled into an "unknown" group — a frequency
        denominator that includes samples of no stated ancestry is not a per-population
        frequency.

        No build-time frequency cut is applied: :meth:`common_haplotypes` already filters
        on ``min_freq`` at query time, and doing it twice would mean a panel whose
        contents depend on a threshold nobody recorded.

        Args:
            path: A phased VCF (plain or gzip-compressed).
            interval: The window to build haplotypes over (0-based half-open).
            sample_populations: Sample ID -> population label.
            source: Panel name recorded on each haplotype (e.g. ``"1000g"``).

        Returns:
            A panel of every haplotype observed in the window.

        Raises:
            ValueError: If the VCF has no ``#CHROM`` header, or carries an **unphased**
                genotype. Unphased calls cannot be assigned to a haplotype, and treating
                ``0/1`` as ``0|1`` would invent phase that was never measured — which is
                the one error this panel must not make, since the engine reports an
                off-target as carried by a named population on the strength of it.
        """
        per_haplotype: dict[tuple[str, int], list[Variant]] = {}
        samples: list[str] = []
        totals: dict[str, int] = defaultdict(int)
        seen_a_site = False

        for line in open_text(path):
            if line.startswith("##") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if line.startswith("#CHROM"):
                samples = cols[9:]
                continue
            if not samples:
                raise ValueError(
                    "phased VCF is missing its '#CHROM ... FORMAT <sample>...' header "
                    "line, so genotype columns cannot be attributed to samples"
                )
            if len(cols) < 10:
                continue
            chrom, pos, ref, alts = cols[0], cols[1], cols[3], cols[4]
            if canonical_contig(chrom) != canonical_contig(interval.chrom):
                continue
            zero_based = int(pos) - 1
            if not interval.start <= zero_based < interval.end:
                continue
            alt_list = alts.split(",")

            if not seen_a_site:
                # Two haplotypes per diploid sample, counted once for the window rather
                # than per site: a per-site denominator would make the frequency depend
                # on how many variants the window happens to contain.
                for name in samples:
                    population = sample_populations.get(name)
                    if population is not None:
                        totals[population] += 2
                seen_a_site = True

            for index, name in enumerate(samples):
                if sample_populations.get(name) is None:
                    continue
                genotype = cols[9 + index].split(":", 1)[0]
                if "/" in genotype:
                    raise ValueError(
                        f"phased VCF carries an unphased genotype {genotype!r} for sample "
                        f"{name!r} at {chrom}:{pos}. A haplotype panel cannot be built "
                        "from unphased calls, and reading '/' as '|' would invent phase "
                        "that was never measured."
                    )
                for which, allele in enumerate(genotype.split("|")):
                    carried = per_haplotype.setdefault((name, which), [])
                    if allele in ("", "."):
                        continue  # missing call: this haplotype carries nothing here
                    try:
                        allele_index = int(allele)
                    except ValueError:
                        continue
                    if allele_index == 0 or allele_index > len(alt_list):
                        continue  # reference, or an index the ALT column cannot supply
                    carried.append(
                        Variant(
                            chrom=chrom,
                            pos=zero_based,
                            ref=ref,
                            alt=alt_list[allele_index - 1],
                        )
                    )

        counts: dict[tuple[Variant, ...], dict[str, int]] = {}
        for (name, _which), carried in per_haplotype.items():
            population = sample_populations[name]
            counts.setdefault(tuple(carried), defaultdict(int))[population] += 1

        ordered = sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))
        haplotypes = [
            Haplotype(
                hap_id=f"{source}-{number}",
                interval=interval,
                variants=key,
                frequencies={
                    population: observed / totals[population]
                    for population, observed in group.items()
                    if totals.get(population)
                },
                source=source,
            )
            for number, (key, group) in enumerate(ordered)
        ]
        return cls(haplotypes, source=source)

    def __iter__(self) -> Iterator[Haplotype]:
        """Iterate every haplotype in the panel, in contig-bucket order.

        The off-target engine consumes a flat ``Iterable[Haplotype]`` and does its
        own overlap, population and frequency filtering, so a caller that has a
        whole panel and no single interval to query — a CLI loading a file, say —
        needs a way to hand the panel over as-is rather than reaching into its
        buckets.
        """
        for haplotypes in self._by_chrom.values():
            yield from haplotypes

    def __len__(self) -> int:
        """Return the number of haplotypes in the panel."""
        return sum(len(h) for h in self._by_chrom.values())

    def common_haplotypes(
        self,
        interval: GenomicInterval,
        *,
        min_freq: float = 0.001,
        populations: Sequence[str] | None = None,
        include_reference: bool = False,
    ) -> list[Haplotype]:
        """Return haplotypes overlapping ``interval`` at frequency >= ``min_freq``.

        Args:
            interval: The query window (0-based half-open).
            min_freq: Minimum per-population frequency to be "common".
            populations: Restrict the frequency test to these populations.
            include_reference: Keep the reference (no-variant) haplotype too.

        Returns:
            Matching haplotypes, sorted by descending max frequency.
        """
        out = [
            hap
            for hap in self._by_chrom.get(canonical_contig(interval.chrom), ())
            if hap.interval.overlaps(interval)
            and (include_reference or not hap.is_reference)
            and hap.max_freq(populations) >= min_freq
        ]
        out.sort(key=lambda h: h.max_freq(populations), reverse=True)
        return out
