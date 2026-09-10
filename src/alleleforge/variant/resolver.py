"""The variant resolver: any input form to one canonical :class:`Variant`.

:func:`resolve` is the front door of the variant-first journey. It accepts a
ClinVar accession, a dbSNP rsID, an HGVS expression (``g.``/``c.``/``p.``), a VCF
record, raw genomic coordinates, or a raw target sequence with a marked position,
and returns a :class:`ResolvedVariant`: the normalized, **left-aligned**,
reference-validated variant plus its working interval, molecular consequence, and
any T2T reference recommendation.

Two invariants from the specification:

* **Left-aligned and parsimonious** (bcftools-norm semantics) when a reference is
  supplied, so the same biological variant from any input form normalizes to one
  canonical record.
* **Reference is validated** — an asserted ``ref`` that disagrees with the
  reference is a hard error (almost always the wrong genome build).
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from alleleforge.genome.coordinates import (
    AmbiguousRegion,
    ReferenceRecommendation,
    flag_ambiguous_regions,
)
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.provenance import DatasetVersion
from alleleforge.types.sequence import (
    CoordinateSystem,
    DNASequence,
    GenomicInterval,
    Strand,
    canonical_contig,
)
from alleleforge.types.variant import (
    ClinicalAssertion,
    ClinVarAccession,
    DbSnpId,
    Variant,
    assembly_matches,
)
from alleleforge.variant.effect import EffectPredictor, VariantEffect
from alleleforge.variant.hgvs_adapter import HgvsAdapter

#: RefSeq chromosome accessions (GRCh38) -> UCSC-style contig names.
_REFSEQ_CHROM: dict[str, str] = {
    **{f"NC_0000{n:02d}": f"chr{n}" for n in range(1, 23)},
    "NC_000023": "chrX",
    "NC_000024": "chrY",
    "NC_012920": "chrM",
}

# The position accepts a leading `-` so a negative coordinate is refused as a *position*
# ("the first base of a contig is position 1") rather than as an unparseable input: the
# string is obviously a coordinate, and saying "unrecognized variant input" of it sends
# the reader to check their syntax, which is fine.
_COORD_RE = re.compile(
    r"^(?P<chrom>[\w.]+):(?P<pos>-?\d+):(?P<ref>[ACGTN]*)>(?P<alt>[ACGTN]*)$",
    re.IGNORECASE,
)
_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_CLINVAR_RE = re.compile(r"^(VCV|RCV|SCV)\d{9}", re.IGNORECASE)
_HGVS_RE = re.compile(r"(?:^|:)[gcpmnr]\.", re.IGNORECASE)


#: What a dispatcher returns: the variant, the input form it came from, and whatever a
#: clinical database asserted about it (``None`` for every non-database form).
_Resolution = tuple[Variant, str, "ClinicalAssertion | None"]


class _ClinVarRecordLike(Protocol):
    """The minimal shape the resolver needs from a ClinVar record.

    Only ``variant`` is required. A real :class:`~alleleforge.data.clinvar.ClinVarRecord`
    also carries the classification, which :func:`_clinical_assertion` reads when
    present — the resolver stays usable with a bare coordinate stub (as tests supply)
    while a full record contributes what the user actually chose the accession for.
    """

    variant: Variant


#: What a caller can actually do about a missing accession/rsID database, per surface.
#: The refusals first named `clinvar=`/`dbsnp=` — the *Python keyword arguments* — to
#: callers who had reached them from `aforge resolve VCV000012345` or a JSON body. The
#: replacement then said the lookups were "Protocols with no shipped implementation",
#: which was simply false: :class:`~alleleforge.data.clinvar.ClinVarDB` and
#: :class:`~alleleforge.data.dbsnp.DbSnpDB` ship, are exported, and implement these
#: Protocols exactly. They are *file-backed*, like `--gnomad`, so every surface that can
#: take a local path can supply one; only HTTP cannot, and for the same reason gnomAD
#: cannot (a client-supplied server path is a file-read primitive).
_DATABASE_REMEDIES: dict[str, str] = {
    "clinvar": (
        "Supply one with `--clinvar <clinvar.vcf.gz>` on the command line, or "
        "`ClinVarDB.from_vcf(path)` from Python. AlleleForge parses the ClinVar VCF "
        "release itself but never downloads it — the registry has no pinned checksum "
        "for it — so the file is yours to provide. Over HTTP there is no such option, "
        "because a client-supplied server path reads the server's files: send "
        "coordinates (chrom:pos:ref>alt, 1-based as in a VCF), which every surface "
        "accepts."
    ),
    "hgvs": (
        "Enable the projector with `--hgvs` on the command line, or "
        "`HgvsAdapter(projector=HgvsLibraryProjector())` from Python — both need the "
        "optional `hgvs` package and a reachable UTA database + SeqRepo, which is why "
        "the projection is opt-in rather than attempted. Over HTTP there is no such "
        "option, because the projection reaches an external service the operator has "
        "not consented to: send coordinates (chrom:pos:ref>alt, 1-based as in a VCF), "
        "or a genomic `g.` expression, which every surface accepts."
    ),
    "dbsnp": (
        "Supply one with `--dbsnp <dbsnp.tsv>` on the command line, or "
        "`DbSnpDB.from_tsv(path)` from Python — an `rsid chrom pos ref alt` "
        "tab-separated file (plain or .gz), with 1-based pos as in a VCF. AlleleForge "
        "never downloads a dbSNP release; the file is yours to provide. Over HTTP "
        "there is no such option, because a client-supplied server path reads the "
        "server's files: send coordinates (chrom:pos:ref>alt, 1-based as in a VCF), "
        "which every surface accepts."
    ),
}


def database_remedy(kind: str) -> str:
    """Return the remedy text for a missing ``kind`` ("clinvar"/"dbsnp") database.

    Kept per-kind rather than shared: one sentence covering both had to name both
    flags on every refusal, and a remedy the reader has to filter is one they will
    mis-apply. Each caller — Python, CLI, HTTP client — is told what *it* can do.
    """
    return _DATABASE_REMEDIES[kind]


class ClinVarLookup(Protocol):
    """A ClinVar database the resolver can query by accession."""

    def get(self, accession: ClinVarAccession | str) -> _ClinVarRecordLike:
        """Return the record for ``accession``."""
        ...


class DbSnpLookup(Protocol):
    """A dbSNP database the resolver can query by rsID."""

    def locus(self, rsid: DbSnpId | str) -> Variant:
        """Return the variant for ``rsid``."""
        ...


class VcfRecord(BaseModel):
    """A single VCF data record (1-based ``pos``, as VCF stores it)."""

    model_config = ConfigDict(frozen=True)

    chrom: str
    pos: int
    ref: str
    alt: str
    rsid: str | None = None

    def to_variant(self) -> Variant:
        """Return the 0-based :class:`Variant` for this record (un-normalized).

        Normalization is deferred to :func:`resolve` so it can validate the *full*
        asserted ref span against the reference first — trimming a shared prefix/
        suffix base here would discard a wrong-build base before it is ever checked.
        """
        return Variant(
            chrom=self.chrom,
            pos=_zero_based(self.chrom, self.pos),
            ref=self.ref,
            alt=self.alt,
            rsid=DbSnpId(value=self.rsid) if self.rsid else None,
        )


class RawTarget(BaseModel):
    """A raw target sequence with a marked edit position (its own reference).

    Attributes:
        sequence: The local reference context, 5'->3' on the plus strand.
        position: 0-based offset of ``ref`` within ``sequence``.
        ref: Reference allele at ``position`` (validated against ``sequence``).
        alt: Alternate allele.
        chrom: A name for the synthetic contig the variant is placed on.
    """

    model_config = ConfigDict(frozen=True)

    sequence: DNASequence
    position: int
    ref: str
    alt: str
    chrom: str = "target"

    @model_validator(mode="after")
    def _check(self) -> RawTarget:
        """Validate the asserted ref matches the embedded sequence."""
        observed = str(self.sequence)[self.position : self.position + len(self.ref)]
        if observed.upper() != self.ref.upper():
            raise ValueError(
                f"asserted ref {self.ref!r} != sequence {observed!r} at position {self.position}"
            )
        return self

    def to_variant(self) -> Variant:
        """Return the normalized :class:`Variant` on the synthetic contig."""
        return Variant(chrom=self.chrom, pos=self.position, ref=self.ref, alt=self.alt).normalized()


#: Every accepted input form for :func:`resolve`.
ResolveInput = Variant | ClinVarAccession | DbSnpId | VcfRecord | RawTarget | str


class ResolvedVariant(BaseModel):
    """The canonical result of resolving any input form.

    Attributes:
        variant: The normalized, left-aligned, reference-validated variant.
        working_interval: The +/- ``window`` analysis interval around it.
        source: The input form it was resolved from (audit aid).
        clinical_assertion: What a clinical database asserts about this variant, when
            resolution came from one. A ClinVar accession is chosen for its
            classification, not its coordinates; carrying only the coordinates left
            every downstream layer unable to say whether it was correcting a
            pathogenic allele or a benign one.
        transcript: The transcript consequence is reported against.
        effect: The molecular consequence, if an effect predictor was supplied.
        reference_recommendation: A T2T recommendation when the locus is
            hg38-ambiguous, else ``None``.
        sources: The version descriptor of each resolution database that actually
            produced this variant. A ClinVar or dbSNP release decides *which locus
            the run is about*, so two runs off different releases can disagree about
            the coordinates for one accession — and the descriptor is the only thing
            that tells those two runs apart. It rides on the resolved variant rather
            than being collected by the caller because a shell that resolves first
            (as the CLI does) hands the design layer nothing but this object.
    """

    model_config = ConfigDict(frozen=True)

    variant: Variant
    working_interval: GenomicInterval
    source: str
    clinical_assertion: ClinicalAssertion | None = None
    transcript: str = "MANE_SELECT"
    effect: VariantEffect | None = None
    reference_recommendation: ReferenceRecommendation | None = None
    sources: tuple[DatasetVersion, ...] = ()


def _chrom_from_hgvs(reference: str | None) -> str:
    """Resolve an HGVS reference prefix to a contig name.

    Raises:
        ValueError: If the prefix is missing or an unmapped RefSeq accession.
    """
    if reference is None:
        raise ValueError("genomic HGVS needs a contig prefix (e.g. 'chr2:g...')")
    if reference.lower().startswith("chr"):
        return reference
    key = reference.split(".")[0]
    if key in _REFSEQ_CHROM:
        return _REFSEQ_CHROM[key]
    raise ValueError(f"cannot map HGVS reference {reference!r} to a contig")


def _zero_based(chrom: str, pos: int) -> int:
    """Convert a 1-based input position to the 0-based one the model stores.

    A non-positive input is refused here rather than by `Variant`'s field validator,
    which sees the *converted* number: `chr11:0:T>C` produced a raw pydantic
    `ValidationError` reading "pos -1 is negative", quoting a coordinate the caller
    never typed, naming an internal model, and linking to the pydantic docs — beside
    a dozen sibling refusals that are one curated sentence. The validator stays as
    the library-level backstop for a caller who builds a `Variant` directly.
    """
    if pos < 1:
        return _refuse_a_non_positive_position(chrom, pos)
    return pos - 1


def _refuse_a_non_positive_position(chrom: str, pos: int) -> int:
    """Raise the refusal for a 1-based position below 1."""
    raise ValueError(
        f"position {pos} on {chrom} is not a valid 1-based coordinate: the first base of "
        "a contig is position 1, as in a VCF record. AlleleForge reads "
        "`chrom:pos:ref>alt` as a 1-based VCF record and prints it with a 0-based "
        "position, so a printed 0 means position 1 on the way back in."
    )


def _from_string(
    text: str,
    *,
    clinvar: ClinVarLookup | None,
    dbsnp: DbSnpLookup | None,
    hgvs: HgvsAdapter | None,
    reference: ReferenceGenome | None,
) -> _Resolution:
    """Dispatch a string input to its variant + source label + any assertion."""
    text = text.strip()
    if _RSID_RE.match(text):
        return _from_dbsnp(DbSnpId(value=text), dbsnp), "rsid", None
    if _CLINVAR_RE.match(text):
        variant, assertion = _from_clinvar(ClinVarAccession(value=text), clinvar)
        return variant, "clinvar", assertion
    if _HGVS_RE.search(text):
        return _from_hgvs(text, hgvs, reference), "hgvs", None
    m = _COORD_RE.match(text)
    if m is None:
        raise ValueError(f"unrecognized variant input: {text!r}{_shell_ate_it(text)}")
    return (
        # Un-normalized on purpose: resolve() validates the full asserted ref span
        # against the reference before parsimony trims a shared prefix/suffix base
        # (which could carry a wrong-build mismatch — see _to_variant / resolve).
        Variant(
            chrom=m.group("chrom"),
            pos=_zero_based(m.group("chrom"), int(m.group("pos"))),
            ref=m.group("ref").upper(),
            alt=m.group("alt").upper(),
        ),
        "coordinates",
        None,
    )


#: A coordinate input with its `>alt` missing: `chrom:pos:ref` and nothing after. This is
#: what every POSIX shell leaves behind when the variant is not quoted, because `>` is
#: output redirection — so `aforge design chr2:71:A>C` writes a file named `C` and hands
#: the tool `chr2:71:A`. The tool's own syntax is hostile to its own command line, and the
#: user sees a string in their history that looks exactly right.
_TRUNCATED_BY_A_SHELL = re.compile(r"^(?P<chrom>[\w.]+):(?P<pos>\d+):(?P<ref>[ACGTNacgtn]*)$")


def _shell_ate_it(text: str) -> str:
    """Return a sentence naming the shell, when the input has the shape it leaves behind.

    Offered only for that exact shape, so an ordinary typo is not told a story about
    redirection it has nothing to do with.
    """
    if not _TRUNCATED_BY_A_SHELL.match(text):
        return ""
    return (
        f". This is `chrom:pos:ref` with no `>alt` — the shape a shell leaves when the "
        f"variant is unquoted, because `>` redirects output (a file named after your ALT "
        f"allele was just created). Quote it: '{text}>ALT'"
    )


def _absent_record(kind: str, key: object, database: object) -> str:
    """Explain a lookup that found no record, in place of a bare ``KeyError``.

    The likeliest thing to go wrong once a release can be supplied is supplying the
    wrong one: a subset, a truncated download, a build that predates the accession, or
    a file that parsed into nothing at all. All four arrived as a raw traceback from
    three frames down — on every shell, since the lookup is reached identically from
    Python, the command line and an HTTP request.

    The record count is the load-bearing detail: `0 record(s)` says the file, not the
    accession, is the problem, and no other output reveals it. The pinned digest lets a
    reader tell which of two releases they actually passed.
    """
    try:
        size = f"{len(database):,} record(s)"  # type: ignore[arg-type]
    except TypeError:  # pragma: no cover - a Protocol implementation need not size itself
        size = "an unknown number of records"
    version = getattr(getattr(database, "dataset_version", None), "version", None)
    named = f" ({version})" if version else ""
    return (
        f"no record for {kind} {key} in the database supplied{named}, which holds {size}. "
        "The release may be a subset, may predate this record, or may have parsed to "
        "nothing — check the file you passed contains it. Resolving by coordinates "
        "(chrom:pos:ref>alt, 1-based as in a VCF) needs no database at all."
    )


def _clinical_assertion(record: _ClinVarRecordLike) -> ClinicalAssertion | None:
    """Return the record's classification, if it carries one.

    Read defensively rather than through the Protocol: the resolver's contract with a
    ClinVar database is deliberately minimal (a coordinate stub is a valid lookup), and
    requiring the classification would break every such stub to gain nothing — a record
    without one simply asserts nothing.
    """
    significance = getattr(record, "significance", None)
    if significance is None:
        return None
    return ClinicalAssertion(
        significance=significance,
        review_status=getattr(record, "review_status", None),
        raw=getattr(record, "raw_significance", None),
    )


def _from_clinvar(
    accession: ClinVarAccession, clinvar: ClinVarLookup | None
) -> tuple[Variant, ClinicalAssertion | None]:
    """Look up a ClinVar accession (requires a ClinVar DB).

    Returns the variant **and** what ClinVar asserts about it. Returning only the
    variant discarded the classification the user chose the accession for, so a design
    could not say whether it was correcting a pathogenic allele or a benign one.
    """
    if clinvar is None:
        raise ValueError(
            f"resolving a ClinVar accession requires a ClinVar database. "
            f"{database_remedy('clinvar')}"
        )
    try:
        record = clinvar.get(accession)
    except KeyError as exc:
        raise ValueError(_absent_record("ClinVar accession", accession, clinvar)) from exc
    return record.variant, _clinical_assertion(record)


def _from_dbsnp(rsid: DbSnpId, dbsnp: DbSnpLookup | None) -> Variant:
    """Look up a dbSNP rsID (requires a dbSNP DB)."""
    if dbsnp is None:
        raise ValueError(
            f"resolving a dbSNP rsID requires a dbSNP database. {database_remedy('dbsnp')}"
        )
    try:
        return dbsnp.locus(rsid)
    except KeyError as exc:
        raise ValueError(_absent_record("dbSNP rsID", rsid, dbsnp)) from exc


def _from_hgvs(text: str, hgvs: HgvsAdapter | None, reference: ReferenceGenome | None) -> Variant:
    """Resolve an HGVS expression to a variant (genomic natively)."""
    adapter = hgvs or HgvsAdapter()
    from alleleforge.variant.hgvs_adapter import parse_genomic_hgvs

    if adapter.is_genomic(text):
        chrom = _chrom_from_hgvs(parse_genomic_hgvs(text).reference)
    else:
        # A c./p. expression: project first, then read its contig prefix.
        projected = adapter._project(text)  # noqa: SLF001 - same package
        chrom = _chrom_from_hgvs(parse_genomic_hgvs(projected).reference)
    # Define the reference accessor only after ``chrom`` is resolved: a c./p. input
    # does not know its contig until the projection above, and a closure that
    # snapshotted the pre-projection ``None`` would crash any coding
    # deletion/dup/delins whose projector omits the reference bases.
    lookup = None
    if reference is not None:

        def lookup(start: int, end: int, _chrom: str = chrom) -> str:
            return str(
                reference.fetch(
                    GenomicInterval(chrom=_chrom, start=start, end=end, strand=Strand.PLUS)
                )
            )

    return adapter.to_variant(text, chrom=chrom, ref_lookup=lookup)


def _to_variant(
    inp: ResolveInput,
    *,
    clinvar: ClinVarLookup | None,
    dbsnp: DbSnpLookup | None,
    hgvs: HgvsAdapter | None,
    reference: ReferenceGenome | None,
) -> _Resolution:
    """Convert any accepted input form to a (variant, source, assertion) triple.

    Coordinate-family inputs (a raw :class:`Variant`, a :class:`VcfRecord`, or a
    ``chrom:pos:ref>alt`` string) are returned **un-normalized** so :func:`resolve`
    can validate their full asserted ref span against the reference before parsimony
    trims a shared prefix/suffix base — otherwise a wrong-build base hidden in that
    trimmed base is silently laundered instead of failing closed. The database/HGVS
    forms validate their asserted bases before this point (RawTarget against its
    embedded sequence, HGVS against the stated ref), so they are already safe.
    """
    if isinstance(inp, Variant):
        return inp, "variant", None
    if isinstance(inp, ClinVarAccession):
        variant, assertion = _from_clinvar(inp, clinvar)
        return variant, "clinvar", assertion
    if isinstance(inp, DbSnpId):
        return _from_dbsnp(inp, dbsnp), "rsid", None
    if isinstance(inp, VcfRecord):
        return inp.to_variant(), "vcf", None
    if isinstance(inp, RawTarget):
        return inp.to_variant(), "raw_sequence", None
    return _from_string(inp, clinvar=clinvar, dbsnp=dbsnp, hgvs=hgvs, reference=reference)


def _ref_base(reference: ReferenceGenome, chrom: str, pos: int) -> str:
    """Return the single plus-strand reference base at 0-based ``pos``."""
    return str(
        reference.fetch(GenomicInterval(chrom=chrom, start=pos, end=pos + 1, strand=Strand.PLUS))
    )


def _left_align(variant: Variant, reference: ReferenceGenome) -> Variant:
    """Left-align and parsimoniously trim an indel against the reference.

    Substitutions and MNVs are returned unchanged. Pure indels are reduced to
    their minimal (anchor-free) representation, rolled as far left as the
    reference repeat structure allows, then re-anchored on the preceding base.
    """
    v = variant.normalized()
    ref, alt, pos = v.ref, v.alt, v.pos
    if len(ref) == len(alt):
        return v  # SNV / MNV: nothing to roll
    # Validate the caller's asserted anchor/flanking base BEFORE re-anchoring. The
    # re-anchor step below re-reads the anchor from the reference, which would
    # overwrite (and so silently accept) a wrong-build insertion whose asserted
    # anchor disagrees — defeating the fail-closed guarantee precisely for
    # insertions. Checking the original assertion first is what closes that hole.
    _validate_ref(v, reference)
    while ref and alt and ref[-1] == alt[-1]:  # strip shared suffix to minimal form
        ref, alt = ref[:-1], alt[:-1]
    while ref and alt and ref[0] == alt[0]:  # strip shared prefix
        ref, alt, pos = ref[1:], alt[1:], pos + 1
    if ref and alt:
        # A true delins (both alleles non-empty after minimal trimming) is not a
        # pure indel: it has no single anchor base to roll and no repeat to roll
        # into. The rolling loop below assumes exactly one allele is empty, so
        # letting a delins fall through would drop its deleted bases entirely.
        return v.model_copy(update={"ref": ref, "alt": alt, "pos": pos})
    while pos > 0:  # roll the indel left through a repeat
        indel = ref if alt == "" else alt
        prev = _ref_base(reference, v.chrom, pos - 1)
        if indel and prev == indel[-1]:
            rolled = prev + indel[:-1]
            ref, alt = (rolled, "") if alt == "" else ("", rolled)
            pos -= 1
        else:
            break
    if pos > 0 and (ref == "" or alt == ""):  # re-anchor on the preceding base
        anchor = _ref_base(reference, v.chrom, pos - 1)
        ref, alt, pos = anchor + ref, anchor + alt, pos - 1
    return v.model_copy(update={"ref": ref, "alt": alt, "pos": pos})


def _ref_matches_at(variant: Variant, reference: ReferenceGenome, pos: int) -> bool:
    """Return whether the asserted ref sits at 0-based ``pos`` in ``reference``."""
    if pos < 0:
        return False
    result = reference.fetch_result(
        GenomicInterval(
            chrom=variant.chrom,
            start=pos,
            end=pos + len(variant.ref),
            strand=Strand.PLUS,
        )
    )
    return not result.padded and str(result.sequence) == variant.ref


def _off_by_one_remedy(variant: Variant, reference: ReferenceGenome) -> str:
    """Return the convention remedy when the ref sits one base away, else ``""``.

    `chrom:pos:ref>alt` is read as a **1-based** VCF record on the way in and printed
    with a **0-based** position on the way out, so this tool does not accept its own
    output: `resolve` prints `chr1:1017:T>A` for the input `chr1:1018:T>A`, and pasting
    that back lands one base left. It either fails here — previously blaming the build,
    which is the one thing that is not wrong — or, when the neighbouring base happens to
    match, silently designs an edit at the wrong locus.

    The evidence is already in hand at the moment of the refusal: if the asserted ref
    sits exactly one base to the right, the caller pasted a printed (0-based) position
    into a 1-based input. One to the left is the reverse conversion.
    """
    if _ref_matches_at(variant, reference, variant.pos + 1):
        return (
            f" — the asserted ref is at {variant.chrom}:{variant.pos + 2} in 1-based "
            f"terms, one base right. AlleleForge reads `chrom:pos:ref>alt` as a 1-based "
            f"VCF record and prints it with a 0-based position, so its own printed "
            f"variant is one lower than the input that produced it; try "
            f"{variant.chrom}:{variant.pos + 2}:{variant.ref}>{variant.alt or '-'}"
        )
    if _ref_matches_at(variant, reference, variant.pos - 1):
        # The mirror case, and it used to be the terse one: " — the asserted ref is one
        # base left; try chr1:15000:C>A", printed under a header reading "reference
        # mismatch at chr1:15000". The same digits twice, meaning two different loci —
        # the header reports the position 0-based, as this tool prints them, and the
        # suggestion is a 1-based input. So the sentence read "position 15000 is wrong;
        # try position 15000", while the branch directly above explained the convention
        # at length. A message about an off-by-one is the last place to leave one
        # unexplained.
        return (
            f" — the asserted ref is one base left, at {variant.chrom}:{variant.pos} in "
            f"1-based terms. This message reports the position 0-based, as AlleleForge "
            f"prints them, while `chrom:pos:ref>alt` is read as a 1-based VCF record, so "
            f"the two positions here are in different conventions even where the digits "
            f"match; try {variant.chrom}:{variant.pos}:{variant.ref}>{variant.alt or '-'}"
        )
    return ""


def _unknown_contig_message(variant: Variant, reference: ReferenceGenome) -> str:
    """Return the refusal for a variant naming a contig the reference does not have.

    Worded like the off-target engine's region refusal, because it is the same mistake
    from the other input: a wrong assembly, a wrong species, or a contig spelling that
    does not reconcile. That one already names the offender and lists what the reference
    does have; this path raised a bare `KeyError` from inside the fetch instead, which is
    the very failure `_reject_unknown_contigs` was written to end — for regions, and only
    for regions.

    Naming reconciliation has already been tried by the time this is reached, so `1` and
    `chr1` are not what gets here; what gets here is genuinely absent.
    """
    available = ", ".join(sorted(reference.contigs)[:8])
    more = "…" if len(reference.contigs) > 8 else ""
    return (
        f"variant names contig {variant.chrom!r}, which this reference does not have "
        f"(it has: {available}{more}). Check the assembly and the contig naming — a "
        "variant on a contig the reference lacks cannot be placed at all."
    )


def _past_the_contig_end_message(variant: Variant, reference: ReferenceGenome) -> str:
    """Return the refusal for a position the contig does not reach.

    The reference does not "have N" there — it has nothing there, and the N is padding
    :meth:`ReferenceGenome.fetch_result` invents so a window near a telomere still
    returns a full-length sequence. Reported as an observed base it produced
    "asserted ref 'A' but reference has 'N' (wrong build?)", which sends a reader to
    liftover for a variant no assembly conversion can rescue: the fault is a coordinate
    outside the contig, usually a truncated FASTA, a chromosome-only file, or a 1-based
    position pasted where a 0-based one was printed.

    The contig's length is known at the moment of the refusal, so it is stated.
    """
    length = reference.contig_length(variant.chrom)
    end = variant.pos + len(variant.ref)
    span = f"{variant.pos}" if len(variant.ref) == 1 else f"{variant.pos}-{end}"
    return (
        f"variant at {variant.chrom}:{span} lies past the end of {variant.chrom}, which "
        f"is {length:,} bases in this reference (0-based positions 0-{length - 1:,}). "
        "Nothing can be validated or designed there. Check that the FASTA is the whole "
        "assembly and not a single chromosome or a truncated copy, and that the "
        "position is the 1-based VCF coordinate this tool reads."
    )


def _validate_ref(variant: Variant, reference: ReferenceGenome) -> None:
    """Raise if the variant's asserted ref disagrees with the reference.

    Raises:
        ValueError: On a ref/reference mismatch, or when the variant names a contig the
            reference does not have, or when the position lies past the contig's end.
            The message names an off-by-one coordinate convention when that is what
            happened, and only blames the build when the allele is nowhere near.
    """
    if not variant.ref:
        return
    try:
        result = reference.fetch_result(
            GenomicInterval(
                chrom=variant.chrom,
                start=variant.pos,
                end=variant.pos + len(variant.ref),
                strand=Strand.PLUS,
            )
        )
    except KeyError as exc:
        # The docstring on `_rename_contig_to_reference` says an unknown contig is left
        # alone "so the existing reference-base validation raises the error it already
        # raises" — but that validation reaches the reference through `fetch_result`,
        # which raises first, from two frames deeper and as a `KeyError`. So the
        # intended message never ran, and `aforge resolve chrZ:101:A>G` printed a
        # traceback: the single likeliest first-run mistake, answered with a stack.
        raise ValueError(_unknown_contig_message(variant, reference)) from exc
    if result.padded:
        # Checked before the mismatch branch, which used to absorb it: the padding is
        # this function's own invention, so reporting it as what the reference holds
        # blames the build for a coordinate the contig never had.
        raise ValueError(_past_the_contig_end_message(variant, reference))
    observed = str(result.sequence)
    if observed != variant.ref:
        remedy = _off_by_one_remedy(variant, reference)
        raise ValueError(
            f"reference mismatch at {variant.chrom}:{variant.pos}: asserted ref "
            f"{variant.ref!r} but reference has {observed!r}" + (remedy or " (wrong build?)")
        )


def _reject_ambiguous_alt(variant: Variant) -> None:
    """Refuse an alt allele carrying ``N``: it is the sequence to be *written*.

    `N` is legitimate in a **ref** — a VCF record at an assembly gap says so, and the
    reference-base check compares it against the genome like any other allele. In an
    **alt** it is not a base anyone can write: no oligo carries it, no editor installs
    it, and no outcome distribution has it as a category. The parser admits `ACGTN` in
    both, so `chr1:15000:C>N` resolved, designed, and then failed inside the pegRNA
    enumerator — which reported *"the RT template spans an assembly gap (N)"*, sending a
    reader to check their FASTA for a gap that is not there. The `N` was in their input.

    Every other IUPAC code is already refused one layer up, by the parser, as an
    unrecognized variant; this makes `N` consistent with them on the side where writing
    is what the allele means.

    Raises:
        ValueError: If the alt allele contains ``N``.
    """
    if "N" in variant.alt:
        raise ValueError(
            f"alt allele {variant.alt!r} contains N, which is not a base that can be "
            "written: the alt is the sequence an edit installs, and no oligo, editor or "
            "outcome distribution can carry an ambiguous base. N in the *ref* is fine — "
            "that is what a VCF record at an assembly gap looks like. Name the base you "
            "want installed, or use a knock-out intent if the point is to disrupt rather "
            "than to write."
        )


def _working_interval(
    variant: Variant, window: int, reference: ReferenceGenome | None
) -> GenomicInterval:
    """Return the +/- ``window`` analysis interval around ``variant``."""
    start = max(0, variant.pos - window)
    end = variant.pos + max(1, len(variant.ref)) + window
    if reference is not None:
        # Clamp through the naming-reconciling accessor, not raw `contigs`
        # membership: a `chr`-named variant against an Ensembl-named reference (the
        # common ClinVar/dbSNP-vs-built-in-hg38 path) is present under its aliased
        # name, so `contig_length` resolves it while `variant.chrom in contigs`
        # would be False and silently skip the clamp, leaking an off-contig end.
        try:
            end = min(end, reference.contig_length(variant.chrom))
        except KeyError:  # genuinely absent (incl. unresolvable naming mismatch)
            pass
    return GenomicInterval(
        chrom=variant.chrom,
        start=start,
        end=end,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )


def _rename_contig_to_reference(variant: Variant, reference: ReferenceGenome) -> Variant:
    """Return ``variant`` with its contig spelled as ``reference`` spells it.

    Only the name changes, and only when the reference has a contig that reconciles
    to the same canonical form. An unknown contig is left alone so the existing
    reference-base validation raises the error it already raises, rather than this
    quietly renaming a variant onto the wrong sequence.

    Args:
        variant: The variant as the caller spelled it.
        reference: The genome it is being resolved against.

    Returns:
        The variant, renamed when the reference knows the contig by another spelling.
    """
    canonical = canonical_contig(variant.chrom)
    for contig in reference.contigs:
        if canonical_contig(contig) == canonical:
            return (
                variant if contig == variant.chrom else variant.model_copy(update={"chrom": contig})
            )
    return variant


def _resolution_sources(
    source: str, *, clinvar: ClinVarLookup | None, dbsnp: DbSnpLookup | None
) -> tuple[DatasetVersion, ...]:
    """Return the version descriptor of the database this variant was resolved from.

    Only the database that actually produced the variant is recorded. A ClinVar
    release passed alongside a coordinate input contributed nothing, and naming it
    would assert that it did — the same overclaim recording a chromatin track made
    when the track never applied.
    """
    # Keyed on the *input form* `source` records, not on the database's name: an
    # rsID is labelled "rsid" and resolves through dbSNP. Getting this wrong is
    # silent — an empty tuple looks exactly like "no descriptor was attached".
    lookup = {"clinvar": clinvar, "rsid": dbsnp}.get(source)
    version = getattr(lookup, "dataset_version", None)
    return (version,) if isinstance(version, DatasetVersion) else ()


def resolve(
    inp: ResolveInput,
    *,
    build: str = "hg38",
    window: int = 100,
    transcript: str = "MANE_SELECT",
    reference: ReferenceGenome | None = None,
    clinvar: ClinVarLookup | None = None,
    dbsnp: DbSnpLookup | None = None,
    hgvs: HgvsAdapter | None = None,
    effect: EffectPredictor | None = None,
    ambiguous_regions: tuple[AmbiguousRegion, ...] | None = None,
) -> ResolvedVariant:
    """Resolve any input form to a canonical :class:`ResolvedVariant`.

    Args:
        inp: A ClinVar accession, dbSNP rsID, HGVS string, :class:`VcfRecord`,
            :class:`RawTarget`, raw ``chrom:pos:ref>alt`` string, or a
            :class:`Variant`.
        build: The reference build the input is expressed in.
        window: Half-width (bp) of the working interval around the variant.
        transcript: Transcript model for consequence calling (MANE Select).
        reference: A :class:`ReferenceGenome` for left-alignment and ref
            validation; when omitted those steps are skipped.
        clinvar: A ClinVar database (needed for accession inputs).
        dbsnp: A dbSNP database (needed for rsID inputs).
        hgvs: An :class:`HgvsAdapter` (needed for ``c.``/``p.`` inputs).
        effect: An :class:`EffectPredictor` to annotate the consequence.
        ambiguous_regions: Override table for hg38-ambiguous-region flagging.

    Returns:
        The canonical :class:`ResolvedVariant`.

    Raises:
        ValueError: On an unrecognized input, a missing required database, or a
            reference mismatch.
    """
    variant, source, assertion = _to_variant(
        inp, clinvar=clinvar, dbsnp=dbsnp, hgvs=hgvs, reference=reference
    )
    # Reconcile — never silently overwrite — a database record's native assembly.
    # A source record that states its assembly must agree with the requested build
    # (no liftover happens here); otherwise the mislabel would poison provenance,
    # the working interval, and the VEP assembly selection downstream.
    if variant.source_assembly is not None and not assembly_matches(variant.source_assembly, build):
        # Every surface gets a remedy it can use. This is raised in the resolver, so it
        # reaches Python, the CLI and an HTTP client alike, and it used to name only
        # `aforge lift` — a shell command a library caller has no reason to reach for and
        # an HTTP client cannot run at all, on the one refusal whose whole purpose is
        # stopping a design at the wrong place in the genome.
        raise ValueError(
            f"source assembly {variant.source_assembly!r} disagrees with requested build "
            f"{build!r}; lift the coordinates to {build!r} before resolving rather than "
            f"relabeling them — `aforge lift <locus> --chain <file> --from "
            f"{variant.source_assembly} --to {build}` on the command line, "
            f"`Liftover.from_chain_file(...)` from Python. Over HTTP there is no lift "
            f"endpoint: lift before sending the request."
        )
    variant = variant.model_copy(update={"build": build})
    _reject_ambiguous_alt(variant)
    if reference is not None:
        # A resolved variant is a position *in this reference*, so it is named the way
        # this reference names it. Contig-style reconciliation already makes the lookup
        # work either way; what it did not do is settle what gets written down, so a
        # `2:71:A>C` input against a `chr2` genome produced a candidate locus of
        # `2:43-63` while the off-target sites found in the same genome said `chr2:…`.
        # The rename is always toward the supplied genome: a bare-named FASTA keeps
        # bare-named output.
        variant = _rename_contig_to_reference(variant, reference)
        # Validate the FULL asserted ref span *before* normalization. `normalized()`
        # (applied inside `_left_align`, and in the no-reference branch below) trims a
        # shared prefix/suffix base whenever ref==alt there — so a wrong-build base in
        # that trimmed position (e.g. asserted `AT>GT` where the reference is `AC`; the
        # unchanged `T` is trimmed to leave `A>G`, which validates) would be laundered
        # away, silently accepting a wrong build and changing the caller's edit. The
        # post-normalization check below only sees the trimmed ref, so this earlier
        # full-span check on the raw assertion is what actually closes the hole.
        _validate_ref(variant, reference)
        variant = _left_align(variant, reference)
        _validate_ref(variant, reference)
    else:
        variant = variant.normalized()

    working = _working_interval(variant, window, reference)
    recommendation = flag_ambiguous_regions(working, source_build=build, regions=ambiguous_regions)
    return ResolvedVariant(
        variant=variant,
        working_interval=working,
        source=source,
        sources=_resolution_sources(source, clinvar=clinvar, dbsnp=dbsnp),
        clinical_assertion=assertion,
        transcript=transcript,
        effect=effect.predict(variant, transcript=transcript) if effect is not None else None,
        reference_recommendation=recommendation if recommendation.recommended else None,
    )
