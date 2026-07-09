"""SpCas9 guide enumeration around a resolved variant.

:func:`enumerate_cas9` finds every PAM-anchored 20-nt protospacer (both strands)
whose predicted blunt cut — **3 bp 5' of the PAM** by default — falls within the
*actionable window* for the requested intent: a tight window around the edit for
precise intents (where HDR efficiency falls off sharply with cut-to-edit
distance), the whole working interval for a knock-out. When no ``NGG`` guide is
actionable, the relaxed ``NG`` (SpCas9-NG) and ``NRN``/``NYN`` (SpRY) PAMs are
emitted only on explicit opt-in.

For a precise-correction intent, :func:`hdr_donor` proposes a homology-directed
repair template carrying the desired allele flanked by reference homology arms,
and — given the guide it must survive — a PAM-blocking silent mutation so the
repaired allele is not re-cleaved.

For a CORRECT/REVERT/INSTALL intent the target genome carries the *alternate*
allele, so the carried allele is substituted onto the fetched window before
protospacers and PAMs are enumerated (mirroring the base-editor and prime
enumerators): a PAM the alternate allele destroys is not emitted, and one it
creates is found.

All coordinates are 0-based half-open; spacers are stored 5'->3' on their own
strand with the genomic placement and strand recorded.
"""

from __future__ import annotations

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import (
    DEFAULT_SPACER_LENGTH,
    PAM,
    BlockingMutation,
    Guide,
    HDRDonor,
    Spacer,
)
from alleleforge.types.sequence import CoordinateSystem, DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant

#: Default blunt-cut offset: 3 bp 5' of the PAM (SpCas9).
DEFAULT_CUT_OFFSET = 3

#: Default actionable radius (bp) around the edit for precise intents. HDR
#: efficiency drops steeply beyond ~10 bp from the cut.
DEFAULT_ACTIONABLE_RADIUS = 10

#: Default HDR homology-arm length (bp) on each side of the edit.
DEFAULT_HDR_ARM = 50

#: Seed length (PAM-proximal nt) used to judge whether a repaired allele still
#: presents the guide's protospacer to Cas9 (matches the prime PE3b convention).
_SEED_LENGTH = 10

#: The primary SpCas9 PAM (module-level singleton; the enumerator default).
NGG_PAM = PAM(pattern="NGG")

#: PAMs tried, in order, when no NGG guide is actionable and opt-in flags are set.
_NG_PAM = PAM(pattern="NG")
_SPRY_PAMS = (PAM(pattern="NRN"), PAM(pattern="NYN"))

_PRECISE_INTENTS = frozenset({EditIntent.CORRECT, EditIntent.REVERT, EditIntent.INSTALL})


def carried_allele(resolved: ResolvedVariant, intent: EditIntent) -> str | None:
    """Return the plus-strand allele the target genome carries at the edit locus.

    For a CORRECT/REVERT intent the target genome carries the alternate allele
    (that is what we are repairing); for INSTALL it carries the reference. A
    non-precise intent (knock-out) returns ``None`` — no substitution applies.
    """
    if intent not in _PRECISE_INTENTS:
        return None
    var = resolved.variant
    return var.alt if intent in (EditIntent.CORRECT, EditIntent.REVERT) else var.ref


def _overlay_allele(sequence: str, *, offset: int, pos: int, ref: str, allele: str) -> str:
    """Return ``sequence`` with ``allele`` substituted for ``ref`` at genomic ``pos``.

    A no-op unless the substitution is length-preserving and fully inside the
    window; coordinate-shifting indels keep the reference frame (the enumerator
    stays reference-based for them, as the prime/base enumerators bail entirely).
    """
    if len(allele) != len(ref):
        return sequence
    rel = pos - offset
    if rel < 0 or rel + len(ref) > len(sequence):
        return sequence
    return sequence[:rel] + allele + sequence[rel + len(ref) :]


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
    intent: EditIntent,
    *,
    reference: ReferenceGenome,
    pam: PAM,
    spacer_length: int,
    cut_offset: int,
    actionable: GenomicInterval,
) -> list[Guide]:
    """Enumerate guides for one PAM whose cut falls within ``actionable``.

    For a precise intent the carried allele is substituted onto the fetched
    window first, so protospacers and PAMs are enumerated against the sequence
    the target genome actually contains — a PAM the alternate allele destroys is
    not emitted, and one it creates is found (mirroring the base/prime paths).
    """
    margin = spacer_length + len(pam.pattern) + cut_offset
    region = GenomicInterval(
        chrom=actionable.chrom,
        start=max(0, actionable.start - margin),
        end=actionable.end + margin,
        strand=Strand.PLUS,
    )
    fetched = reference.fetch_result(region)
    sequence = str(fetched.sequence)
    carried = carried_allele(resolved, intent)
    if carried is not None:
        var = resolved.variant
        sequence = _overlay_allele(
            sequence, offset=region.start, pos=var.pos, ref=var.ref, allele=carried
        )
    guides = _enumerate_window(
        sequence,
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
        intent,
        reference=reference,
        pam=pam,
        spacer_length=spacer_length,
        cut_offset=cut_offset,
        actionable=actionable,
    )
    if not guides and allow_ng:
        guides = _enumerate_pam(
            resolved,
            intent,
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
                intent,
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


def guide_context(
    guide: Guide,
    reference: ReferenceGenome,
    *,
    flank: int = 6,
    flank_5: int | None = None,
    flank_3: int | None = None,
    overlay: tuple[int, str, str] | None = None,
) -> str:
    """Return the sequence context around a guide (5'->3' on the guide's strand).

    Spans the protospacer, its PAM, and flanking bases — the window an efficiency
    model reads. ``flank`` is a symmetric margin; ``flank_5`` / ``flank_3`` override
    it per side (5' and 3' in the guide's own orientation). The trained Rule Set 3
    model, for instance, wants an asymmetric 30-mer: 4 nt 5' + 20 nt protospacer +
    3 nt PAM + 3 nt 3' (``flank_5=4, flank_3=3``).

    ``overlay`` is a plus-strand ``(pos, ref, allele)`` substitution applied before
    the strand is resolved, so on-target scoring reads the carried allele rather
    than the reference at a variant inside the window.
    """
    f5 = flank if flank_5 is None else flank_5
    f3 = flank if flank_3 is None else flank_3
    pam_len = len(guide.pam.pattern)
    placement = guide.placement
    if placement.strand is Strand.PLUS:
        lo, hi = placement.start - f5, placement.end + pam_len + f3
    else:
        lo, hi = placement.start - pam_len - f3, placement.end + f5
    lo = max(0, lo)
    plus = str(
        reference.fetch(
            GenomicInterval(chrom=placement.chrom, start=lo, end=hi, strand=Strand.PLUS)
        )
    )
    if overlay is not None:
        pos, ref_base, allele = overlay
        plus = _overlay_allele(plus, offset=lo, pos=pos, ref=ref_base, allele=allele)
    if placement.strand is Strand.MINUS:
        return str(DNASequence(plus).reverse_complement())
    return plus


def _corrected_span(
    guide: Guide, var_pos: int, var_ref: str, desired: str, reference: ReferenceGenome
) -> tuple[int, str]:
    """Return ``(lo, plus)``: the repaired plus-strand sequence over the guide.

    Spans the guide's protospacer and PAM with the ``desired`` allele installed —
    the sequence Cas9 would face after HDR repair.
    """
    placement = guide.placement
    pam_len = len(guide.pam.pattern)
    if placement.strand is Strand.PLUS:
        lo, hi = placement.start, placement.end + pam_len
    else:
        lo, hi = placement.start - pam_len, placement.end
    lo = max(0, lo)
    plus = str(
        reference.fetch(
            GenomicInterval(chrom=placement.chrom, start=lo, end=hi, strand=Strand.PLUS)
        )
    )
    return lo, _overlay_allele(plus, offset=lo, pos=var_pos, ref=var_ref, allele=desired)


def _pam_matches(guide: Guide, lo: int, plus: str) -> bool:
    """Return ``True`` if the guide's PAM still matches over the plus span ``plus``."""
    placement = guide.placement
    pam_len = len(guide.pam.pattern)
    if placement.strand is Strand.PLUS:
        start = placement.end - lo
        pam_seq = plus[start : start + pam_len]
    else:
        end = placement.start - lo
        pam_seq = str(DNASequence(plus[end - pam_len : end]).reverse_complement())
    return len(pam_seq) == pam_len and guide.pam.matches(pam_seq)


def _seed_intact(guide: Guide, lo: int, plus: str) -> bool:
    """Return ``True`` if the repaired protospacer still matches the guide's seed."""
    placement = guide.placement
    spacer = str(guide.spacer.sequence)
    if placement.strand is Strand.PLUS:
        start = placement.start - lo
        proto = plus[start : start + len(spacer)]
    else:
        end = placement.end - lo
        proto = str(DNASequence(plus[end - len(spacer) : end]).reverse_complement())
    seed_len = min(_SEED_LENGTH, len(spacer), len(proto))
    # The Cas9 seed is the PAM-proximal end — the 3' end of the 5'->3' spacer.
    return proto[-seed_len:] == spacer[-seed_len:]


def _find_pam_block(
    guide: Guide,
    lo: int,
    corrected: str,
    *,
    var_pos: int,
    var_ref: str,
    left_start: int,
    right_start: int,
    right_end: int,
) -> BlockingMutation | None:
    """Find a single PAM base, inside a homology arm, whose change breaks the PAM."""
    placement = guide.placement
    pam_len = len(guide.pam.pattern)
    pam_start = placement.end if placement.strand is Strand.PLUS else placement.start - pam_len
    for pos in range(pam_start, pam_start + pam_len):
        in_arm = (left_start <= pos < var_pos) or (right_start <= pos < right_end)
        if not in_arm or var_pos <= pos < var_pos + len(var_ref):
            continue  # outside the donor, or overlapping the edit itself
        idx = pos - lo
        if idx < 0 or idx >= len(corrected):
            continue
        current = corrected[idx]
        for base in "ACGT":
            if base == current:
                continue
            trial = corrected[:idx] + base + corrected[idx + 1 :]
            if not _pam_matches(guide, lo, trial):
                return BlockingMutation(
                    position=pos, reference_base=current, donor_base=base, region="pam"
                )
    return None


def _donor_index(
    pos: int, *, var_pos: int, left_start: int, right_start: int, desired_len: int
) -> int:
    """Map a genomic position in a homology arm to its index in the donor string."""
    if pos < var_pos:
        return pos - left_start
    return (var_pos - left_start) + desired_len + (pos - right_start)


def hdr_donor(
    resolved: ResolvedVariant,
    intent: EditIntent,
    *,
    reference: ReferenceGenome,
    guide: Guide | None = None,
    arm_length: int = DEFAULT_HDR_ARM,
) -> HDRDonor | None:
    """Propose an HDR donor template for a precise intent (else ``None``).

    The donor carries the *desired* allele — the reference allele for
    ``correct``/``revert``, the alternate allele for ``install`` — flanked by
    ``arm_length`` bp of reference homology on each side. A knock-out intent has
    no precise template and returns ``None``.

    When ``guide`` is supplied, the donor is checked against re-cutting: if the
    repaired product still presents the guide's PAM and seed, a PAM-blocking
    silent mutation is introduced in a homology arm (and recorded) so the corrected
    allele is not a Cas9 substrate; if none is available, the donor is returned
    with ``recut_blocked = False`` and a note saying so, never silently re-cuttable.
    """
    if intent not in _PRECISE_INTENTS:
        return None
    var = resolved.variant
    desired = var.ref if intent in (EditIntent.CORRECT, EditIntent.REVERT) else var.alt
    left_start = max(0, var.pos - arm_length)
    right_start = var.pos + len(var.ref)
    right_end = right_start + arm_length
    left = str(
        reference.fetch(
            GenomicInterval(chrom=var.chrom, start=left_start, end=var.pos, strand=Strand.PLUS)
        )
    )
    right = str(
        reference.fetch(
            GenomicInterval(chrom=var.chrom, start=right_start, end=right_end, strand=Strand.PLUS)
        )
    )
    donor_seq = f"{left}{desired}{right}"

    if guide is None:
        return HDRDonor(
            sequence=DNASequence(donor_seq),
            recut_blocked=False,
            note="no guide supplied; re-cut disposition not assessed",
        )

    lo, corrected = _corrected_span(guide, var.pos, var.ref, desired, reference)
    if not (_pam_matches(guide, lo, corrected) and _seed_intact(guide, lo, corrected)):
        return HDRDonor(
            sequence=DNASequence(donor_seq),
            recut_blocked=True,
            note="the correcting edit itself disrupts the guide PAM or seed",
        )

    mutation = _find_pam_block(
        guide,
        lo,
        corrected,
        var_pos=var.pos,
        var_ref=var.ref,
        left_start=left_start,
        right_start=right_start,
        right_end=right_end,
    )
    if mutation is None:
        return HDRDonor(
            sequence=DNASequence(donor_seq),
            recut_blocked=False,
            note=(
                "no PAM-blocking mutation available in a homology arm; "
                "donor remains a Cas9 substrate"
            ),
        )
    idx = _donor_index(
        mutation.position,
        var_pos=var.pos,
        left_start=left_start,
        right_start=right_start,
        desired_len=len(desired),
    )
    blocked = donor_seq[:idx] + mutation.donor_base + donor_seq[idx + 1 :]
    return HDRDonor(
        sequence=DNASequence(blocked),
        blocking_mutation=mutation,
        recut_blocked=True,
        note=(
            f"PAM-blocking mutation {var.chrom}:{mutation.position} "
            f"{mutation.reference_base}>{mutation.donor_base}; "
            "confirm it is synonymous in your reading frame"
        ),
    )
