"""Prime-editing pegRNA enumeration — the flagship chemistry.

Prime editing installs an arbitrary small edit without a double-strand break. The
Cas9(H840A) nickase nicks the PAM-containing strand 3 bp 5' of the PAM; the
nicked 3' end primes on the pegRNA's **PBS** (primer-binding site), and reverse
transcriptase copies the **RTT** (RT template) — which encodes the edit plus 3'
homology — onto the genome.

:func:`enumerate_prime` finds every pegRNA that can install a variant's edit:
for each PAM whose nick sits 5' of the edit (within RT reach), it enumerates
**PBS (8-17 nt)** and **RTT (7-34 nt, covering the edit + >= 5 nt 3' homology)**,
attaches a **tevopreQ1** epegRNA 3' motif by default, and selects a **PE3/PE3b
nicking guide** (preferring a seed-disrupting PE3b ngRNA, which nicks only the
edited strand and so reduces indels). Both strands are handled by enumerating in
a reverse-complemented frame for minus-strand pegRNAs.

The RTT is templated at **variable length**, so the full prime-editing repertoire
is enumerated: substitutions (SNV/MNV), short insertions, short deletions, and
delins. The RT template always reads *5' homology (nick to edit) + the desired
allele + 3' homology*, so a deletion simply omits the removed bases (its span
costs no RTT length) while an insertion pays for every templated base. The
practical limits follow from :data:`~alleleforge.types.guide.RTT_RANGE`:
:data:`PRIME_MAX_TEMPLATED_EDIT` bounds the allele the RTT must *write*, and
:data:`PRIME_MAX_EDIT` bounds the reference span it may replace.

Enumeration runs over the **start genome** — the reference window with the allele
the target genome actually carries substituted in — whose coordinates drift from
the reference downstream of a length-changing edit.
:class:`~alleleforge.enumerate._frame.EditFrame` owns that mapping so every emitted
placement is a truthful *reference* interval.

The design layer (:mod:`alleleforge.design.prime`) scores efficiency / outcome
and runs the off-target engine on both nicks.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence

from alleleforge.enumerate._frame import EditFrame
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import (
    DEFAULT_SPACER_LENGTH,
    MIN_RTT_3PRIME_HOMOLOGY,
    PAM,
    PBS_RANGE,
    RTT_RANGE,
    NickingGuide,
    PegRNA,
    Spacer,
    ThreePrimeMotif,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.variant.resolver import ResolvedVariant

#: The canonical SpCas9 sgRNA scaffold used for pegRNAs.
SCAFFOLD = "GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGCTAGTCCGTTATCAACTTGAAAAAGTGGCACCGAGTCGGTGC"

#: Default blunt-nick offset: 3 bp 5' of the PAM (SpCas9 nickase).
DEFAULT_CUT_OFFSET = 3

#: The primary SpCas9 PAM.
NGG_PAM = PAM(pattern="NGG")

#: PE3 nicking-guide optimal nick-to-nick offset range (nt, opposite strand).
DEFAULT_PE3_OFFSET = (40, 90)

#: Longest reference span (bp) a pegRNA may replace or delete. Beyond this the
#: edit is better served by nuclease-plus-HDR or a larger tool. A deleted span
#: costs no RT template, so this bound is independent of the RTT budget.
PRIME_MAX_EDIT = 44

#: Longest allele (bp) an RTT can *template*. The RT template must carry the
#: whole desired allele plus the minimum 3' homology inside ``RTT_RANGE``, so an
#: insertion or replacement longer than this cannot be written at any nick.
PRIME_MAX_TEMPLATED_EDIT = RTT_RANGE[1] - MIN_RTT_3PRIME_HOMOLOGY

#: The ngRNA seed length (PAM-proximal nt) used to classify PE3b.
_SEED_LENGTH = 10


def _rc(seq: str) -> str:
    """Return the reverse complement of ``seq``."""
    return str(DNASequence(seq).reverse_complement())


def _required_alleles(resolved: ResolvedVariant, intent: EditIntent) -> tuple[str, str]:
    """Return the ``(start_allele, desired_allele)`` on the plus strand."""
    var = resolved.variant
    if intent in (EditIntent.CORRECT, EditIntent.REVERT):
        return var.alt, var.ref  # the genome carries the variant; restore the reference
    return var.ref, var.alt  # install the alternate allele


def _select_nicking_guide(
    start: str,
    edited: str,
    *,
    edit_local: int,
    pegrna_nick_local: int,
    pam: PAM,
    spacer_length: int,
    cut_offset: int,
    frame: EditFrame,
    pegrna_nick_genomic: int,
    pe3_offset: tuple[int, int],
) -> NickingGuide | None:
    """Select a PE3/PE3b nicking guide on the strand opposite the pegRNA nick.

    The ngRNA is a normal NGG guide in the *frame-minus* strand (opposite the
    pegRNA's frame-plus nick). PE3b — an ngRNA whose seed spans the edit, so it
    nicks only the edited strand — is preferred; otherwise a PE3 ngRNA whose nick
    falls in the optimal offset range is chosen.
    """
    pam_len = len(pam.pattern)
    pe3b: NickingGuide | None = None
    pe3: NickingGuide | None = None
    for k in range(len(start) - pam_len + 1):
        # frame-minus PAM reads NGG on the opposite strand (revcomp here).
        if not pam.matches(_rc(start[k : k + pam_len])):
            continue
        proto_lo = k + pam_len
        proto_hi = proto_lo + spacer_length
        if proto_hi > len(start) or "N" in start[proto_lo:proto_hi]:
            continue
        nick_local = proto_lo + cut_offset  # nick on the opposite strand (frame coords)
        offset = nick_local - pegrna_nick_local
        placement = frame.interval(proto_lo, proto_hi, Strand.MINUS)
        if placement is None:
            continue  # no reference locus for this protospacer; cannot be placed
        nick_genomic = frame.coord(nick_local)
        # The ngRNA protospacer reads on the minus strand, so its PAM-proximal end
        # (where the Cas9 seed lives) is the LOW genomic boundary ``proto_lo``,
        # adjacent to the PAM at ``[k, k+pam_len)``. The seed is therefore the
        # SEED_LENGTH bases from ``proto_lo`` up — an edit disrupts it iff
        # ``edit_local - proto_lo < _SEED_LENGTH``. Measuring from ``proto_hi`` (the
        # PAM-distal 5' end) mislabels a genuine PE3b as plain PE3 and falsely
        # promotes a PAM-distal edit to PE3b.
        #
        # ``proto_lo <= edit_local`` also keeps the ngRNA's PAM and seed inside the
        # prefix ``start`` and ``edited`` share, so the *same* index addresses the
        # same locus in both — the precondition for templating the PE3b spacer from
        # ``edited`` at all. Past the edit a length-changing variant shifts the two
        # strings apart, and the comparison below would read misaligned windows.
        # Disruption is then decided by comparing the seed windows themselves
        # rather than a single base, which is what an indel actually changes.
        seed_disrupting = (
            proto_lo <= edit_local
            and edit_local - proto_lo < _SEED_LENGTH
            and proto_hi <= len(edited)
            and start[proto_lo : proto_lo + _SEED_LENGTH]
            != edited[proto_lo : proto_lo + _SEED_LENGTH]
        )
        # A PE3b ngRNA must match the *edited* strand so its seed base-pairs only
        # after the edit is installed — that temporal separation (it mismatches the
        # unedited allele) is the whole PE3b benefit. Templating the spacer from
        # ``start`` would nick the *unedited* molecule and fail on the edited
        # product, the exact inverse of the guarantee. A PE3 ngRNA lies away from
        # the edit, where ``start`` and ``edited`` agree, so ``start`` is fine there.
        template = edited if seed_disrupting else start
        spacer = _rc(template[proto_lo:proto_hi])
        guide = NickingGuide(
            spacer=Spacer(sequence=DNASequence(spacer)),
            placement=placement,
            nick_offset=nick_genomic - pegrna_nick_genomic,
            seed_disrupting=seed_disrupting,
        )
        if seed_disrupting:
            pe3b = guide
            break
        if pe3 is None and pe3_offset[0] <= abs(offset) <= pe3_offset[1]:
            pe3 = guide
    return pe3b or pe3


#: Why a candidate protospacer was rejected, in the words a user needs. When prime
#: enumeration returns nothing the report used to say only "eligible but no actionable
#: candidate enumerated", which tells a scientist that their flagship chemistry found
#: nothing and not whether to try the other strand, a different PAM, or another
#: chemistry entirely. These distinguish the cases that have different remedies.
REJECTION_REASONS: dict[str, str] = {
    "no-pam": "no PAM match at this offset",
    "ambiguous": "the protospacer or PAM spans an assembly gap (N)",
    "pol3-terminator": "the spacer contains TTTT, which terminates Pol III transcription",
    "edit-5-prime-of-nick": (
        "the edit lies 5' of the nick, which an RTT extending 3' cannot reach"
    ),
    "pbs-out-of-range": "no PBS length in range fits before the nick",
    "rtt-out-of-range": (
        "the nick-to-edit distance plus the edit and its 3' homology needs an RTT "
        "outside the synthesizable range"
    ),
    "rtt-past-window": "the RTT would run past the fetched reference window",
    "rtt-spans-gap": "the RT template spans an assembly gap (N)",
}


def _note(tally: MutableMapping[str, int] | None, reason: str) -> None:
    """Record one rejection, when a caller asked for the tally."""
    if tally is not None:
        tally[reason] = tally.get(reason, 0) + 1


def rejection_summary(tally: Mapping[str, int]) -> str:
    """Render a rejection tally as one sentence, most common reason first."""
    counted = [(n, k) for k, n in tally.items() if n and k in REJECTION_REASONS]
    if not counted:
        return "no protospacer was examined"
    counted.sort(key=lambda kv: (-kv[0], kv[1]))
    return "; ".join(f"{REJECTION_REASONS[k]} ({n})" for n, k in counted)


def _enumerate_frame(
    start: str,
    edited: str,
    *,
    edit_local: int,
    edit_len: int,
    spacer_length: int,
    cut_offset: int,
    pam: PAM,
    pbs_lengths: Sequence[int],
    rtt_homologies: Sequence[int],
    motif: ThreePrimeMotif,
    pe3: bool,
    pe3_offset: tuple[int, int],
    frame: EditFrame,
    frame_strand: Strand,
    tally: MutableMapping[str, int] | None = None,
) -> list[PegRNA]:
    """Enumerate frame-plus pegRNAs (the strand whose protospacer is ``start``).

    ``edit_local`` is the index at which the edit begins — the same index in
    ``start`` and ``edited``, which share that prefix — and ``edit_len`` is the
    length of the **desired** allele, i.e. how many bases the RTT must write
    there (0 for a pure deletion).
    """
    pam_len = len(pam.pattern)
    out: list[PegRNA] = []
    for k in range(spacer_length, len(start) - pam_len + 1):
        if "N" in start[k : k + pam_len] or not pam.matches(start[k : k + pam_len]):
            _note(tally, "no-pam")
            continue
        proto = start[k - spacer_length : k]
        if "N" in proto:
            _note(tally, "ambiguous")
            continue
        if "TTTT" in proto:
            _note(tally, "pol3-terminator")
            continue  # Pol III terminator: pegRNA cannot be transcribed
        nick_local = k - cut_offset
        distance = edit_local - nick_local  # edit must be 3' of the nick (>= 0)
        if distance < 0:
            _note(tally, "edit-5-prime-of-nick")
            continue
        placement = frame.interval(k - spacer_length, k, frame_strand)
        nick_genomic = frame.coord(nick_local)
        nicking = (
            _select_nicking_guide(
                start,
                edited,
                edit_local=edit_local,
                pegrna_nick_local=nick_local,
                pam=pam,
                spacer_length=spacer_length,
                cut_offset=cut_offset,
                frame=frame,
                pegrna_nick_genomic=nick_genomic,
                pe3_offset=pe3_offset,
            )
            if pe3
            else None
        )
        for pbs_len in pbs_lengths:
            if nick_local - pbs_len < 0 or not PBS_RANGE[0] <= pbs_len <= PBS_RANGE[1]:
                _note(tally, "pbs-out-of-range")
                continue
            pbs = _rc(start[nick_local - pbs_len : nick_local])
            for homology in rtt_homologies:
                rtt_len = distance + edit_len + homology
                if not RTT_RANGE[0] <= rtt_len <= RTT_RANGE[1]:
                    _note(tally, "rtt-out-of-range")
                    continue
                if nick_local + rtt_len > len(edited):
                    _note(tally, "rtt-past-window")
                    continue
                rtt_window = edited[nick_local : nick_local + rtt_len]
                if "N" in rtt_window:
                    _note(tally, "rtt-spans-gap")
                    # The RT template spans an assembly-gap N (the reference is unknown
                    # there). Skip it, mirroring the spacer/PAM N-guards above and the
                    # per-span guards in the cas9/base-editor enumerators: a pegRNA whose
                    # RTT carries an N is an unsynthesizable oligo that, if forced, would
                    # template an ambiguous base into the genome exactly at the gap.
                    continue
                rtt = _rc(rtt_window)
                out.append(
                    PegRNA(
                        spacer=Spacer(sequence=DNASequence(proto)),
                        scaffold=DNASequence(SCAFFOLD),
                        rtt=DNASequence(rtt),
                        pbs=DNASequence(pbs),
                        three_prime_motif=motif,
                        rtt_homology_5prime=distance,
                        rtt_homology_3prime=homology,
                        nicking_guide=nicking,
                        placement=placement,
                        nick_site=nick_genomic,
                    )
                )
    return out


def enumerate_prime(
    resolved: ResolvedVariant,
    intent: EditIntent = EditIntent.CORRECT,
    *,
    reference: ReferenceGenome,
    pam: PAM = NGG_PAM,
    spacer_length: int = DEFAULT_SPACER_LENGTH,
    cut_offset: int = DEFAULT_CUT_OFFSET,
    pbs_lengths: Sequence[int] = tuple(range(PBS_RANGE[0], PBS_RANGE[1] + 1)),
    rtt_homologies: Sequence[int] = tuple(range(5, 14)),
    motif: ThreePrimeMotif = ThreePrimeMotif.TEVOPREQ1,
    pe3: bool = True,
    pe3_offset: tuple[int, int] = DEFAULT_PE3_OFFSET,
    tally: MutableMapping[str, int] | None = None,
) -> list[PegRNA]:
    """Enumerate pegRNAs that install a variant's edit (both strands).

    Handles the full small-edit repertoire — substitution, MNV, insertion,
    deletion, and delins — by templating a variable-length RTT.

    Args:
        resolved: The resolved variant to install or correct.
        intent: What the edit must accomplish (sets start/desired alleles).
        reference: The reference genome.
        pam: The pegRNA PAM (default ``NGG``).
        spacer_length: Protospacer length (default 20).
        cut_offset: Nick distance 5' of the PAM (default 3).
        pbs_lengths: PBS lengths to enumerate (default 8-17).
        rtt_homologies: 3'-homology lengths to enumerate (>= 5).
        motif: The epegRNA 3' motif (default tevopreQ1).
        pe3: Select a PE3/PE3b nicking guide (default on).
        pe3_offset: Optimal PE3 nick-to-nick offset range.
        tally: Optional mapping the reason for each rejected protospacer is counted
            into, so a caller that enumerated nothing can say *why* rather than only
            that it found nothing. One dict increment per rejection, and nothing at
            all when omitted.

    Returns:
        Validated :class:`PegRNA`s (with placement, nick site, and an attached
        nicking guide), sorted by nick site then PBS then RTT length. Empty when
        the edit is a no-op, replaces more than :data:`PRIME_MAX_EDIT` reference
        bases, or must template more than :data:`PRIME_MAX_TEMPLATED_EDIT` bases
        (no RTT inside ``RTT_RANGE`` can carry it plus its 3' homology).
    """
    var = resolved.variant
    start_allele, desired_allele = _required_alleles(resolved, intent)
    if start_allele == desired_allele:
        return []  # nothing to write
    if len(var.ref) > PRIME_MAX_EDIT or len(var.alt) > PRIME_MAX_EDIT:
        return []  # beyond the practical prime-editing span
    if len(desired_allele) > PRIME_MAX_TEMPLATED_EDIT:
        return []  # no RTT in range can template the desired allele + 3' homology
    ref_len = len(var.ref)
    margin = (
        spacer_length
        + len(pam.pattern)
        + RTT_RANGE[1]
        + max(pbs_lengths, default=PBS_RANGE[1])
        + max(ref_len, len(start_allele), len(desired_allele))
    )
    region = GenomicInterval(
        chrom=var.chrom,
        start=max(0, var.pos - margin),
        end=var.pos + margin,
        strand=Strand.PLUS,
    )
    fetched = reference.fetch_result(region)
    plus = str(fetched.sequence)
    rel = var.pos - region.start
    prefix, suffix = plus[:rel], plus[rel + ref_len :]
    start_plus = prefix + start_allele + suffix
    edited_plus = prefix + desired_allele + suffix
    offset = region.start

    plus_frame = EditFrame(
        chrom=var.chrom,
        offset=offset,
        edit_plus=rel,
        start_len=len(start_allele),
        ref_len=ref_len,
        span=len(start_plus),
        reverse=False,
    )
    minus_frame = EditFrame(
        chrom=var.chrom,
        offset=offset,
        edit_plus=rel,
        start_len=len(start_allele),
        ref_len=ref_len,
        span=len(start_plus),
        reverse=True,
    )
    # In the reverse-complemented frame the shared *suffix* becomes the shared
    # prefix, so the edit begins that many bases in — the one index that addresses
    # the edit identically in both the start and edited strings of that frame.
    minus_edit_local = len(suffix)

    def run(start: str, edited: str, edit_local: int, frame: EditFrame) -> list[PegRNA]:
        return _enumerate_frame(
            start,
            edited,
            edit_local=edit_local,
            edit_len=len(desired_allele),
            spacer_length=spacer_length,
            cut_offset=cut_offset,
            pam=pam,
            pbs_lengths=pbs_lengths,
            rtt_homologies=rtt_homologies,
            motif=motif,
            pe3=pe3,
            pe3_offset=pe3_offset,
            frame=frame,
            tally=tally,
            frame_strand=Strand.PLUS,
        )

    results = run(start_plus, edited_plus, rel, plus_frame)
    results += run(_rc(start_plus), _rc(edited_plus), minus_edit_local, minus_frame)
    results.sort(key=lambda p: (p.nick_site or 0, len(p.pbs), len(p.rtt)))
    return results
