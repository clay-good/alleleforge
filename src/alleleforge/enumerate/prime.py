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

The design layer (:mod:`alleleforge.design.prime`) scores efficiency / outcome
and runs the off-target engine on both nicks.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import (
    DEFAULT_SPACER_LENGTH,
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

#: The ngRNA seed length (PAM-proximal nt) used to classify PE3b.
_SEED_LENGTH = 10

#: Maps a frame-local ``(lo, hi, frame_strand)`` to a genomic interval.
_Placer = Callable[[int, int, Strand], GenomicInterval]


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
    place: _Placer,
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
        spacer = _rc(start[proto_lo:proto_hi])
        placement = place(proto_lo, proto_hi, Strand.MINUS)
        nick_genomic = place(nick_local, nick_local + 1, Strand.MINUS).start
        # The ngRNA protospacer reads on the minus strand, so its PAM-proximal end
        # (where the Cas9 seed lives) is the LOW genomic boundary ``proto_lo``,
        # adjacent to the PAM at ``[k, k+pam_len)``. The seed is therefore the
        # SEED_LENGTH bases from ``proto_lo`` up — an edit disrupts it iff
        # ``edit_local - proto_lo < _SEED_LENGTH``. Measuring from ``proto_hi`` (the
        # PAM-distal 5' end) mislabels a genuine PE3b as plain PE3 and falsely
        # promotes a PAM-distal edit to PE3b.
        seed_disrupting = (
            proto_lo <= edit_local < proto_hi
            and (edit_local - proto_lo) < _SEED_LENGTH
            and start[edit_local] != edited[edit_local]
        )
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


def _enumerate_frame(
    start: str,
    edited: str,
    *,
    edit_local: int,
    spacer_length: int,
    cut_offset: int,
    pam: PAM,
    pbs_lengths: Sequence[int],
    rtt_homologies: Sequence[int],
    motif: ThreePrimeMotif,
    pe3: bool,
    pe3_offset: tuple[int, int],
    place: _Placer,
    frame_strand: Strand,
) -> list[PegRNA]:
    """Enumerate frame-plus pegRNAs (the strand whose protospacer is ``start``)."""
    pam_len = len(pam.pattern)
    edit_len = 1  # SNV / single-position edit on the (equal-length) templates
    out: list[PegRNA] = []
    for k in range(spacer_length, len(start) - pam_len + 1):
        if "N" in start[k : k + pam_len] or not pam.matches(start[k : k + pam_len]):
            continue
        proto = start[k - spacer_length : k]
        if "N" in proto:
            continue
        if "TTTT" in proto:
            continue  # Pol III terminator in the spacer: pegRNA cannot be transcribed
        nick_local = k - cut_offset
        distance = edit_local - nick_local  # edit must be 3' of the nick (>= 0)
        if distance < 0:
            continue
        placement = place(k - spacer_length, k, frame_strand)
        nick_genomic = place(nick_local, nick_local + 1, frame_strand).start
        nicking = (
            _select_nicking_guide(
                start,
                edited,
                edit_local=edit_local,
                pegrna_nick_local=nick_local,
                pam=pam,
                spacer_length=spacer_length,
                cut_offset=cut_offset,
                place=place,
                pegrna_nick_genomic=nick_genomic,
                pe3_offset=pe3_offset,
            )
            if pe3
            else None
        )
        for pbs_len in pbs_lengths:
            if nick_local - pbs_len < 0 or not PBS_RANGE[0] <= pbs_len <= PBS_RANGE[1]:
                continue
            pbs = _rc(start[nick_local - pbs_len : nick_local])
            for homology in rtt_homologies:
                rtt_len = distance + edit_len + homology
                if not RTT_RANGE[0] <= rtt_len <= RTT_RANGE[1]:
                    continue
                if nick_local + rtt_len > len(edited):
                    continue
                rtt = _rc(edited[nick_local : nick_local + rtt_len])
                out.append(
                    PegRNA(
                        spacer=Spacer(sequence=DNASequence(proto)),
                        scaffold=DNASequence(SCAFFOLD),
                        rtt=DNASequence(rtt),
                        pbs=DNASequence(pbs),
                        three_prime_motif=motif,
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
) -> list[PegRNA]:
    """Enumerate pegRNAs that install a variant's edit (both strands).

    Args:
        resolved: The resolved variant (SNV / single-position edit).
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

    Returns:
        Validated :class:`PegRNA`s (with placement, nick site, and an attached
        nicking guide), sorted by nick site then PBS then RTT length. Empty when
        the variant is not a single-position edit.
    """
    var = resolved.variant
    if len(var.ref) != 1 or len(var.alt) != 1:
        return []  # the equal-length template path supports single-position edits
    start_allele, desired_allele = _required_alleles(resolved, intent)
    margin = (
        spacer_length
        + len(pam.pattern)
        + max(rtt_homologies, default=5)
        + max(pbs_lengths, default=PBS_RANGE[1])
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
    start_plus = plus[:rel] + start_allele + plus[rel + 1 :]
    edited_plus = plus[:rel] + desired_allele + plus[rel + 1 :]
    n = len(plus)
    offset = region.start

    def place_plus(lo: int, hi: int, strand: Strand) -> GenomicInterval:
        return GenomicInterval(chrom=var.chrom, start=offset + lo, end=offset + hi, strand=strand)

    def place_minus(lo: int, hi: int, strand: Strand) -> GenomicInterval:
        return GenomicInterval(
            chrom=var.chrom, start=offset + n - hi, end=offset + n - lo, strand=strand.opposite()
        )

    def run(start: str, edited: str, edit_local: int, place: _Placer) -> list[PegRNA]:
        return _enumerate_frame(
            start,
            edited,
            edit_local=edit_local,
            spacer_length=spacer_length,
            cut_offset=cut_offset,
            pam=pam,
            pbs_lengths=pbs_lengths,
            rtt_homologies=rtt_homologies,
            motif=motif,
            pe3=pe3,
            pe3_offset=pe3_offset,
            place=place,
            frame_strand=Strand.PLUS,
        )

    results = run(start_plus, edited_plus, rel, place_plus)
    results += run(_rc(start_plus), _rc(edited_plus), n - 1 - rel, place_minus)
    results.sort(key=lambda p: (p.nick_site or 0, len(p.pbs), len(p.rtt)))
    return results
