"""SpCas9 guide enumeration around a resolved variant.

:func:`enumerate_cas9` finds every PAM-anchored 20-nt protospacer (both strands)
whose predicted blunt cut — **3 bp 5' of the PAM** by default — falls within the
*actionable window* for the requested intent: a tight window around the edit for
precise intents (where HDR efficiency falls off sharply with cut-to-edit
distance), the whole working interval for a knock-out. When no ``NGG`` guide is
actionable, the relaxed ``NG`` (SpCas9-NG) and ``NRN``/``NYN`` (SpRY) PAMs are
emitted only on explicit opt-in.

For a precise-correction intent, :func:`hdr_donor` proposes a homology-directed
repair template carrying the desired allele flanked by reference homology arms.

All coordinates are 0-based half-open; spacers are stored 5'->3' on their own
strand with the genomic placement and strand recorded.
"""

from __future__ import annotations

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import DEFAULT_SPACER_LENGTH, PAM, Guide, Spacer
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant

#: Default blunt-cut offset: 3 bp 5' of the PAM (SpCas9).
DEFAULT_CUT_OFFSET = 3

#: Default actionable radius (bp) around the edit for precise intents. HDR
#: efficiency drops steeply beyond ~10 bp from the cut.
DEFAULT_ACTIONABLE_RADIUS = 10

#: Default HDR homology-arm length (bp) on each side of the edit.
DEFAULT_HDR_ARM = 50

#: The primary SpCas9 PAM (module-level singleton; the enumerator default).
NGG_PAM = PAM(pattern="NGG")

#: PAMs tried, in order, when no NGG guide is actionable and opt-in flags are set.
_NG_PAM = PAM(pattern="NG")
_SPRY_PAMS = (PAM(pattern="NRN"), PAM(pattern="NYN"))

_PRECISE_INTENTS = frozenset({EditIntent.CORRECT, EditIntent.REVERT, EditIntent.INSTALL})


def _actionable_window(
    resolved: ResolvedVariant, intent: EditIntent, radius: int
) -> GenomicInterval:
    """Return the interval a cut must fall within to achieve ``intent``."""
    if intent is EditIntent.KNOCK_OUT:
        return resolved.working_interval
    var = resolved.variant
    start = max(0, var.pos - radius)
    end = var.pos + max(1, len(var.ref)) + radius
    return GenomicInterval(
        chrom=var.chrom,
        start=start,
        end=end,
        strand=Strand.PLUS,
        coordinate_system=CoordinateSystem.ZERO_BASED_HALF_OPEN,
    )


def _enumerate_window(
    sequence: str,
    *,
    chrom: str,
    offset: int,
    pam: PAM,
    spacer_length: int,
    cut_offset: int,
) -> list[Guide]:
    """Enumerate PAM-anchored guides on both strands of ``sequence``.

    ``sequence`` is plus-strand; ``offset`` maps it back to genome coordinates.
    """
    pam_len = len(pam.pattern)
    guides: list[Guide] = []
    for k in range(len(sequence) - pam_len + 1):
        window = sequence[k : k + pam_len]
        # Plus strand: PAM reads 5'->3' directly; protospacer is 5' of it.
        if k >= spacer_length and pam.matches(window) and "N" not in window:
            proto = sequence[k - spacer_length : k]
            if "N" not in proto:
                pam_start = offset + k
                guides.append(
                    Guide(
                        spacer=Spacer(sequence=DNASequence(proto)),
                        pam=pam,
                        pam_sequence=DNASequence(window),
                        placement=GenomicInterval(
                            chrom=chrom,
                            start=offset + k - spacer_length,
                            end=pam_start,
                            strand=Strand.PLUS,
                        ),
                        cut_site=pam_start - cut_offset,
                    )
                )
        # Minus strand: the PAM reads NGG on the minus strand, i.e. revcomp here.
        rc_window = str(DNASequence(window).reverse_complement())
        proto_end = k + pam_len + spacer_length
        if proto_end <= len(sequence) and pam.matches(rc_window) and "N" not in rc_window:
            proto_plus = sequence[k + pam_len : proto_end]
            if "N" not in proto_plus:
                spacer = str(DNASequence(proto_plus).reverse_complement())
                proto_start = offset + k + pam_len
                guides.append(
                    Guide(
                        spacer=Spacer(sequence=DNASequence(spacer)),
                        pam=pam,
                        pam_sequence=DNASequence(rc_window),
                        placement=GenomicInterval(
                            chrom=chrom,
                            start=proto_start,
                            end=proto_start + spacer_length,
                            strand=Strand.MINUS,
                        ),
                        cut_site=proto_start + cut_offset,
                    )
                )
    return guides


def _enumerate_pam(
    resolved: ResolvedVariant,
    *,
    reference: ReferenceGenome,
    pam: PAM,
    spacer_length: int,
    cut_offset: int,
    actionable: GenomicInterval,
) -> list[Guide]:
    """Enumerate guides for one PAM whose cut falls within ``actionable``."""
    margin = spacer_length + len(pam.pattern) + cut_offset
    region = GenomicInterval(
        chrom=actionable.chrom,
        start=max(0, actionable.start - margin),
        end=actionable.end + margin,
        strand=Strand.PLUS,
    )
    fetched = reference.fetch_result(region)
    guides = _enumerate_window(
        str(fetched.sequence),
        chrom=region.chrom,
        offset=region.start,
        pam=pam,
        spacer_length=spacer_length,
        cut_offset=cut_offset,
    )
    return [g for g in guides if actionable.start <= g.cut_site < actionable.end]


def enumerate_cas9(
    resolved: ResolvedVariant,
    intent: EditIntent,
    *,
    reference: ReferenceGenome,
    pam: PAM = NGG_PAM,
    spacer_length: int = DEFAULT_SPACER_LENGTH,
    cut_offset: int = DEFAULT_CUT_OFFSET,
    actionable_radius: int = DEFAULT_ACTIONABLE_RADIUS,
    allow_ng: bool = False,
    allow_spry: bool = False,
) -> list[Guide]:
    """Enumerate actionable SpCas9 guides for a resolved variant.

    Args:
        resolved: The resolved variant (provides the edit site and working window).
        intent: What the edit must accomplish (sets the actionable window).
        reference: The reference genome.
        pam: The primary PAM (default ``NGG``).
        spacer_length: Protospacer length (default 20).
        cut_offset: Blunt cut distance 5' of the PAM (default 3).
        actionable_radius: Half-width (bp) of the precise-intent actionable window.
        allow_ng: Emit ``NG`` (SpCas9-NG) guides if no ``NGG`` guide is actionable.
        allow_spry: Emit ``NRN``/``NYN`` (SpRY) guides if still none.

    Returns:
        Guides whose cut falls within the actionable window, sorted by cut site
        then strand. Falls back to relaxed PAMs only when ``NGG`` yields none and
        the corresponding flag is set.
    """
    actionable = _actionable_window(resolved, intent, actionable_radius)
    guides = _enumerate_pam(
        resolved,
        reference=reference,
        pam=pam,
        spacer_length=spacer_length,
        cut_offset=cut_offset,
        actionable=actionable,
    )
    if not guides and allow_ng:
        guides = _enumerate_pam(
            resolved,
            reference=reference,
            pam=_NG_PAM,
            spacer_length=spacer_length,
            cut_offset=cut_offset,
            actionable=actionable,
        )
    if not guides and allow_spry:
        for spry in _SPRY_PAMS:
            guides = _enumerate_pam(
                resolved,
                reference=reference,
                pam=spry,
                spacer_length=spacer_length,
                cut_offset=cut_offset,
                actionable=actionable,
            )
            if guides:
                break
    guides.sort(key=lambda g: (g.cut_site, g.placement.strand.value))
    return guides


def guide_context(guide: Guide, reference: ReferenceGenome, *, flank: int = 6) -> str:
    """Return the sequence context around a guide (5'->3' on the guide's strand).

    Spans the protospacer, its PAM, and ``flank`` extra bases on each side — the
    window an efficiency model reads (e.g. Rule Set 3's 30-mer).
    """
    pam_len = len(guide.pam.pattern)
    placement = guide.placement
    if placement.strand is Strand.PLUS:
        lo, hi = placement.start, placement.end + pam_len
    else:
        lo, hi = placement.start - pam_len, placement.end
    interval = GenomicInterval(
        chrom=placement.chrom,
        start=max(0, lo - flank),
        end=hi + flank,
        strand=placement.strand,
    )
    return str(reference.fetch(interval))


def hdr_donor(
    resolved: ResolvedVariant,
    intent: EditIntent,
    *,
    reference: ReferenceGenome,
    arm_length: int = DEFAULT_HDR_ARM,
) -> DNASequence | None:
    """Propose an HDR donor template for a precise intent (else ``None``).

    The donor carries the *desired* allele — the reference allele for
    ``correct``/``revert``, the alternate allele for ``install`` — flanked by
    ``arm_length`` bp of reference homology on each side. A knock-out intent has
    no precise template and returns ``None``.
    """
    if intent not in _PRECISE_INTENTS:
        return None
    var = resolved.variant
    desired = var.ref if intent in (EditIntent.CORRECT, EditIntent.REVERT) else var.alt
    left = reference.fetch(
        GenomicInterval(
            chrom=var.chrom, start=max(0, var.pos - arm_length), end=var.pos, strand=Strand.PLUS
        )
    )
    right = reference.fetch(
        GenomicInterval(
            chrom=var.chrom,
            start=var.pos + len(var.ref),
            end=var.pos + len(var.ref) + arm_length,
            strand=Strand.PLUS,
        )
    )
    return DNASequence(f"{left}{desired}{right}")
