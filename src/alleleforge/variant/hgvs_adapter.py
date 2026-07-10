"""HGVS parsing and projection for the variant resolver.

Two responsibilities:

* :func:`parse_genomic_hgvs` is a dependency-free parser for **genomic** (``g.``)
  HGVS expressions (substitution, deletion, insertion, duplication, delins),
  enough to take a ``g.`` string straight to coordinates without the heavy
  ``hgvs`` library — so CI never needs it.
* :class:`HgvsAdapter` turns a parsed ``g.`` expression into a
  :class:`~alleleforge.types.variant.Variant` (filling implicit deleted bases
  from a reference), and projects **coding/protein** (``c.``/``p.``) expressions
  through an injected projector. In production that projector wraps the ``hgvs``
  library against MANE Select; in tests it is a small fake.

Genomic HGVS positions are 1-based; the parser converts them to AlleleForge's
0-based coordinates.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from alleleforge.types.variant import Variant

#: ``reference:`` prefix (RefSeq accession or contig) is optional and captured.
_PREFIX_RE = re.compile(r"^(?:(?P<ref>[^:]+):)?(?P<kind>[gcpmnr])\.(?P<rest>.+)$")

_SUB_RE = re.compile(r"^(?P<pos>\d+)(?P<r>[ACGTN])>(?P<a>[ACGTN])$")
_RANGE_RE = re.compile(
    r"^(?P<start>\d+)(?:_(?P<end>\d+))?"
    r"(?P<op>delins|del|ins|dup)(?P<bases>[ACGTN]*)$"
)


class HgvsOp(StrEnum):
    """The genomic edit operation a ``g.`` expression encodes."""

    SUB = "sub"
    DEL = "del"
    INS = "ins"
    DUP = "dup"
    DELINS = "delins"


class ParsedGenomicHgvs(BaseModel):
    """A parsed genomic HGVS expression in 0-based coordinates.

    Attributes:
        reference: The RefSeq accession or contig prefix, if present.
        op: The edit operation.
        start: 0-based start of the affected reference span.
        end: 0-based half-open end of the affected reference span.
        ref_bases: Reference bases, if the expression stated them (else ``None``).
        alt_bases: Inserted/replacement bases (``""`` for a plain deletion).
    """

    model_config = ConfigDict(frozen=True)

    reference: str | None
    op: HgvsOp
    start: int
    end: int
    ref_bases: str | None
    alt_bases: str


def parse_genomic_hgvs(text: str) -> ParsedGenomicHgvs:
    """Parse a genomic (``g.``) HGVS expression.

    Args:
        text: e.g. ``"NC_000002.12:g.60100A>T"``, ``"chr2:g.60100_60102del"``,
            or a bare ``"g.60100_60101insAC"``.

    Returns:
        A :class:`ParsedGenomicHgvs` with 0-based coordinates.

    Raises:
        ValueError: If ``text`` is not a recognized genomic HGVS expression.
    """
    m = _PREFIX_RE.match(text.strip())
    if m is None or m.group("kind") != "g":
        raise ValueError(f"not a genomic (g.) HGVS expression: {text!r}")
    reference = m.group("ref")
    rest = m.group("rest")

    sub = _SUB_RE.match(rest)
    if sub is not None:
        pos0 = int(sub.group("pos")) - 1
        return ParsedGenomicHgvs(
            reference=reference,
            op=HgvsOp.SUB,
            start=pos0,
            end=pos0 + 1,
            ref_bases=sub.group("r"),
            alt_bases=sub.group("a"),
        )

    rng = _RANGE_RE.match(rest)
    if rng is None:
        raise ValueError(f"unsupported genomic HGVS expression: {text!r}")
    start1 = int(rng.group("start"))
    end1 = int(rng.group("end")) if rng.group("end") else start1
    # A range whose end precedes its start (e.g. `g.5_3del`, `g.5_3delinsAC`) is not a
    # valid span. Fail closed: an un-guarded reversed range makes `ref_lookup(start, end)`
    # read a backwards, empty Python slice, so the deleted/duplicated bases silently
    # vanish and a delins collapses into a pure insertion that deletes nothing — a phantom
    # variant accepted with no error, the wrong side of the "raise on malformed input" line.
    if end1 < start1:
        raise ValueError(f"range end precedes start: {text!r}")
    op = HgvsOp(rng.group("op"))
    bases = rng.group("bases")
    start0, end0 = start1 - 1, end1
    if op is HgvsOp.INS:
        # An insertion sits *between* the two stated 1-based positions; the
        # affected reference span is empty and anchored before the right base.
        if not bases:
            raise ValueError(f"insertion needs inserted bases: {text!r}")
        return ParsedGenomicHgvs(
            reference=reference, op=op, start=end1 - 1, end=end1 - 1, ref_bases="", alt_bases=bases
        )
    if op is HgvsOp.DEL:
        return ParsedGenomicHgvs(
            reference=reference,
            op=op,
            start=start0,
            end=end0,
            ref_bases=bases or None,
            alt_bases="",
        )
    if op is HgvsOp.DUP:
        # `ref_bases` holds the (optionally stated) duplicated span over
        # [start, end); :meth:`HgvsAdapter.to_variant` turns it into an insertion.
        return ParsedGenomicHgvs(
            reference=reference,
            op=op,
            start=start0,
            end=end0,
            ref_bases=bases or None,
            alt_bases="",
        )
    # delins: replacement bases are stated; the deleted span is read from the ref.
    if not bases:
        raise ValueError(f"delins needs replacement bases: {text!r}")
    return ParsedGenomicHgvs(
        reference=reference, op=op, start=start0, end=end0, ref_bases=None, alt_bases=bases
    )


#: A projector maps a coding/protein HGVS string to a genomic ``g.`` string,
#: typically by wrapping the ``hgvs`` library against MANE Select. Injected so
#: tests never need the library.
HgvsProjector = Callable[[str], str]


class HgvsLibraryProjector:
    """A :data:`HgvsProjector` backed by the real ``hgvs`` library (UTA/SeqRepo).

    Wraps Biocommons ``hgvs``: parse the ``c.``/``n.`` expression, project it to
    the genomic ``g.`` expression on the requested assembly via an
    :class:`AssemblyMapper` (which resolves transcript→genome alignments from a
    UTA database and reference sequence from SeqRepo). The library and its data
    services are **optional** and reached only on the production path — never in
    CI; tests inject a fake projector instead. The library handles is constructed
    lazily on first call and cached.

    Args:
        assembly: Target assembly name (``"GRCh38"`` default).
        alt_aln_method: Transcript-alignment method UTA exposes (``"splign"``).
    """

    def __init__(self, *, assembly: str = "GRCh38", alt_aln_method: str = "splign") -> None:
        """Record the assembly and alignment method; defer the heavy setup."""
        self._assembly = assembly
        self._alt_aln_method = alt_aln_method
        self._parser: object | None = None
        self._mapper: object | None = None

    def _ensure_backend(self) -> None:
        """Construct the ``hgvs`` parser + assembly mapper on first use.

        Raises:
            RuntimeError: If the optional ``hgvs`` package is not installed.
        """
        if self._mapper is not None:  # pragma: no cover - reached only after a live connect
            return
        try:
            import hgvs.assemblymapper
            import hgvs.dataproviders.uta  # pragma: no cover - reached only with hgvs installed
            import hgvs.parser  # pragma: no cover - reached only with hgvs installed
        except ImportError as exc:
            raise RuntimeError(
                "HgvsLibraryProjector requires the optional 'hgvs' package "
                "(and a reachable UTA database + SeqRepo)"
            ) from exc
        # The rest needs a live UTA connection + SeqRepo, never reached in CI.
        hdp = hgvs.dataproviders.uta.connect()  # pragma: no cover - network (UTA)
        self._parser = hgvs.parser.Parser()  # pragma: no cover - needs hgvs data
        self._mapper = hgvs.assemblymapper.AssemblyMapper(  # pragma: no cover - needs hgvs data
            hdp, assembly_name=self._assembly, alt_aln_method=self._alt_aln_method
        )

    def __call__(self, text: str) -> str:
        """Project a ``c.``/``n.`` expression to a genomic ``g.`` string."""
        self._ensure_backend()
        assert self._parser is not None and self._mapper is not None  # pragma: no cover - live only
        parsed = self._parser.parse_hgvs_variant(text)  # type: ignore[attr-defined]  # pragma: no cover
        return str(self._mapper.c_to_g(parsed))  # type: ignore[attr-defined]  # pragma: no cover


class HgvsAdapter:
    """Resolve HGVS expressions to :class:`Variant`s.

    ``g.`` is handled natively; ``c.``/``p.`` are first projected to ``g.`` via
    an injected :data:`HgvsProjector` (the ``hgvs`` library in production).
    """

    def __init__(self, *, projector: HgvsProjector | None = None) -> None:
        """Configure the adapter with an optional coding/protein projector."""
        self._projector = projector

    def is_genomic(self, text: str) -> bool:
        """Return ``True`` if ``text`` is a genomic (``g.``) expression."""
        m = _PREFIX_RE.match(text.strip())
        return m is not None and m.group("kind") == "g"

    def to_variant(
        self,
        text: str,
        *,
        chrom: str,
        ref_lookup: Callable[[int, int], str] | None = None,
    ) -> Variant:
        """Resolve an HGVS expression to a normalized genomic :class:`Variant`.

        Args:
            text: A ``g.``/``c.``/``p.`` HGVS expression.
            chrom: The contig name to place the variant on.
            ref_lookup: ``(start0, end0) -> bases`` reference accessor, required
                to fill the deleted bases of a deletion/duplication that did not
                state them.

        Returns:
            A normalized :class:`Variant` (with ``hgvs_g`` recorded).

        Raises:
            ValueError: For a ``c.``/``p.`` input when no projector is set, or a
                deletion/dup needing reference bases without a ``ref_lookup``.
        """
        genomic = text if self.is_genomic(text) else self._project(text)
        parsed = parse_genomic_hgvs(genomic)
        if parsed.op is HgvsOp.DUP:
            # A duplication is an insertion of the duplicated span just after it.
            if parsed.ref_bases is not None:
                self._check_stated_bases(
                    ref_lookup, parsed.start, parsed.end, parsed.ref_bases, "dup"
                )
                dup_bases = parsed.ref_bases
            else:
                dup_bases = self._fill(ref_lookup, parsed.start, parsed.end, "dup")
            return self._variant(chrom, parsed.end, "", dup_bases, text)
        ref_bases = parsed.ref_bases
        if parsed.op in (HgvsOp.DEL, HgvsOp.DELINS):
            if ref_bases is None:
                ref_bases = self._fill(ref_lookup, parsed.start, parsed.end, parsed.op.value)
            else:
                self._check_stated_bases(
                    ref_lookup, parsed.start, parsed.end, ref_bases, parsed.op.value
                )
        return self._variant(chrom, parsed.start, ref_bases or "", parsed.alt_bases, text)

    @staticmethod
    def _variant(chrom: str, pos: int, ref: str, alt: str, hgvs_g: str) -> Variant:
        """Build and normalize a genomic :class:`Variant`."""
        return Variant(chrom=chrom, pos=pos, ref=ref, alt=alt, hgvs_g=hgvs_g).normalized()

    @staticmethod
    def _fill(ref_lookup: Callable[[int, int], str] | None, start: int, end: int, op: str) -> str:
        """Read ``[start, end)`` reference bases, or raise if no accessor given."""
        if ref_lookup is None:
            raise ValueError(f"{op} needs a reference to fill its bases")
        return ref_lookup(start, end)

    @staticmethod
    def _check_stated_bases(
        ref_lookup: Callable[[int, int], str] | None,
        start: int,
        end: int,
        stated: str,
        op: str,
    ) -> None:
        """Assert caller-stated ``del``/``dup`` bases agree with the reference span.

        A ``del``/``dup``/``delins`` may state the deleted/duplicated bases (legal
        HGVS, emitted by real tools). Those bases must equal ``reference[start:end)``;
        when they do not — a wrong genome build, or a span length that contradicts
        the stated bases — that is a hard error, exactly as an asserted ``sub``/``del``
        ref that disagrees is. Trusting them silently fabricates an insertion or a
        mis-sized deletion. Without a reference (``ref_lookup is None``) the bases
        cannot be checked and are trusted, as before.
        """
        if ref_lookup is None:
            return
        actual = ref_lookup(start, end)
        if stated.upper() != actual.upper():
            raise ValueError(
                f"{op} reference mismatch at [{start}, {end}): stated {stated!r} but "
                f"reference has {actual!r} (usually the wrong genome build)"
            )

    def _project(self, text: str) -> str:
        """Project a ``c.``/``p.`` expression to ``g.`` via the projector."""
        if self._projector is None:
            raise ValueError(f"coding/protein HGVS {text!r} needs a projector (the 'hgvs' library)")
        return self._projector(text)
