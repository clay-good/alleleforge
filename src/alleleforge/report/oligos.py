"""Cloning-ready oligo synthesis for every chemistry.

Bench scientists order **annealed oligo pairs**, not abstract spacers. This
module turns a scored :class:`~alleleforge.types.candidate.DesignCandidate` into
the exact oligonucleotides to order and anneal for standard Golden-Gate cloning:

* **SpCas9 / base-editor sgRNAs** — one duplex with vector-appropriate 5'
  overhangs, optionally prepending the U6 transcription-start ``G``.
* **pegRNAs** — the spacer duplex plus the 3' extension duplex (RTT + PBS, with
  the epegRNA 3' motif appended), cloned against the constant scaffold.
* **ngRNAs** — the PE3/PE3b nicking guide as a standard sgRNA duplex.

Every scheme is **named** and **parameterized** (enzyme, overhangs, whether a
5' ``G`` is added). The cardinal invariant, enforced by :meth:`reconstruct` on
each oligo set and exercised by the tests, is that **round-tripping the oligos
recovers the intended spacer / RTT / PBS** — a design whose oligos do not
reconstruct is a cloning error waiting to happen.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from alleleforge.enumerate.prime import SCAFFOLD
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.guide import PegRNA, ThreePrimeMotif

_COMPLEMENT = str.maketrans("ACGTN", "TGCAN")

#: The concrete DNA alphabet a wet-lab oligo may contain.
_DNA_ALPHABET = frozenset("ACGTN")


def _require_dna(seq: str, *, context: str) -> str:
    """Return ``seq`` upper-cased, or raise if it holds a non-``ACGTN`` character.

    A wet-lab oligo is ordered and annealed verbatim, so a stray RNA ``U``, an
    IUPAC ambiguity code, or whitespace is a wrong reagent, not a soft warning.
    """
    up = seq.upper()
    bad = sorted(set(up) - _DNA_ALPHABET)
    if bad:
        raise ValueError(
            f"{context} contains non-DNA character(s) {bad}; a wet-lab oligo must be ACGTN only"
        )
    return up


def revcomp(seq: str) -> str:
    """Return the reverse complement of a concrete ACGTN sequence.

    Raises:
        ValueError: If ``seq`` contains any character outside ``ACGTN`` (e.g. an
            RNA ``U`` or an IUPAC ambiguity code), which ``str.maketrans`` would
            otherwise pass through untranslated and emit a mis-complemented oligo.
    """
    return _require_dna(seq, context="reverse-complement input").translate(_COMPLEMENT)[::-1]


#: Engineered 3' epegRNA motif sequences (DNA form), appended after the PBS.
#: tevopreQ1 = an 8-nt linker + the evopreQ1 pseudoknot (Nelson, Randolph et al.,
#: *Nat Biotechnol* 2022); mpknot is the Mpknot pseudoknot from the same work.
MOTIF_SEQUENCES: dict[ThreePrimeMotif, str] = {
    ThreePrimeMotif.NONE: "",
    ThreePrimeMotif.TEVOPREQ1: "GAAACCCGGCGCGGTTCTATCTAGTTACGCGTTAAACCAACTAGAA",
    ThreePrimeMotif.MPKNOT: "GAAACCCGGTGCCAGGCCCGGGAATTGGAGCCGCCTAGGCCAACCC",
}


class VectorScheme(BaseModel):
    """A named cloning scheme: enzyme, sticky-end overhangs, and the U6 ``G``.

    Attributes:
        name: Human-readable scheme name (echoed into the oligo set).
        enzyme: The Type IIS enzyme whose overhangs this scheme matches.
        top_overhang: 5' overhang prepended to the sense oligo.
        bottom_overhang: 5' overhang prepended to the antisense oligo.
        prepend_g: Add a 5' ``G`` to the spacer for U6 transcription start.
        citation: Protocol citation.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    enzyme: str
    top_overhang: str
    bottom_overhang: str
    prepend_g: bool = True
    citation: str | None = None


#: lentiGuide-Puro / lentiCRISPRv2 sgRNA cloning (BsmBI; CACC / AAAC overhangs).
LENTIGUIDE_BSMBI = VectorScheme(
    name="lentiguide-bsmbi",
    enzyme="BsmBI",
    top_overhang="CACC",
    bottom_overhang="AAAC",
    prepend_g=True,
    citation="Sanjana, Shalem & Zhang, Nat Methods 2014 (lentiCRISPRv2/lentiGuide)",
)

#: pX330 / pSpCas9(BB) sgRNA cloning (BbsI; same CACC / AAAC overhangs).
PX330_BBSI = VectorScheme(
    name="px330-bbsi",
    enzyme="BbsI",
    top_overhang="CACC",
    bottom_overhang="AAAC",
    prepend_g=True,
    citation="Ran et al., Nat Protoc 2013 (pX330 / pSpCas9(BB))",
)

#: Standard pegRNA Golden-Gate acceptor (BsaI). The spacer duplex uses the U6
#: CACC/AAAC ends; the 3' extension duplex uses GTGC/CGCG ends that ligate the
#: extension downstream of the scaffold.
PEGRNA_GG_BSAI = VectorScheme(
    name="pegrna-gg-bsai",
    enzyme="BsaI",
    top_overhang="CACC",
    bottom_overhang="AAAC",
    prepend_g=True,
    citation="Anzalone et al., Nature 2019 (pU6-pegRNA-GG-acceptor)",
)

#: 5' / 3' overhangs ligating the pegRNA 3' extension (RTT+PBS+motif) in-frame
#: downstream of the scaffold in the GG acceptor.
_EXT_TOP_OVERHANG = "GTGC"
_EXT_BOTTOM_OVERHANG = "AAAA"


class SgRnaOligos(BaseModel):
    """An annealed sgRNA oligo duplex for one spacer.

    Attributes:
        kind: ``"sgrna"`` (Cas9), ``"base-editor-sgrna"``, or ``"ngrna"``.
        spacer: The intended 5'->3' spacer (the reconstruction target).
        top: The sense oligo to order (5'->3').
        bottom: The antisense oligo to order (5'->3').
        scheme: The cloning scheme used.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    spacer: str
    top: str
    bottom: str
    scheme: VectorScheme

    def reconstruct(self) -> str:
        """Recover the spacer from the oligos (round-trip check).

        Raises:
            ValueError: If the oligos do not reconstruct a consistent spacer.
        """
        if not self.top.startswith(self.scheme.top_overhang):
            raise ValueError("top oligo missing the scheme's 5' overhang")
        core = self.top[len(self.scheme.top_overhang) :]
        if self.scheme.prepend_g:
            if not core.startswith("G"):
                raise ValueError("top oligo missing the U6 transcription-start G")
            core = core[1:]
        expected_bottom = self.scheme.bottom_overhang + revcomp(
            ("G" if self.scheme.prepend_g else "") + core
        )
        if self.bottom != expected_bottom:
            raise ValueError("antisense oligo is not the reverse complement of the sense oligo")
        if core != self.spacer:
            raise ValueError("oligo does not reconstruct its declared spacer")
        return core


class PegRNAOligos(BaseModel):
    """The annealed oligo duplexes for one pegRNA (spacer + 3' extension).

    Attributes:
        spacer: The intended pegRNA spacer (reconstruction target).
        rtt: The intended RTT (reconstruction target).
        pbs: The intended PBS (reconstruction target).
        motif: The 3' epegRNA motif attached to the extension.
        scaffold: The constant sgRNA scaffold (cloned from the vector).
        spacer_top: Sense spacer oligo (5'->3').
        spacer_bottom: Antisense spacer oligo (5'->3').
        ext_top: Sense 3'-extension oligo: RTT + PBS + motif (5'->3').
        ext_bottom: Antisense 3'-extension oligo (5'->3').
        nicking: The ngRNA oligo duplex, when a PE3/PE3b guide is present.
        scheme: The cloning scheme used.
    """

    model_config = ConfigDict(frozen=True)

    spacer: str
    rtt: str
    pbs: str
    motif: ThreePrimeMotif
    scaffold: str
    spacer_top: str
    spacer_bottom: str
    ext_top: str
    ext_bottom: str
    nicking: SgRnaOligos | None
    scheme: VectorScheme

    def reconstruct(self) -> tuple[str, str, str]:
        """Recover ``(spacer, rtt, pbs)`` from the oligos (round-trip check).

        Raises:
            ValueError: If any duplex fails to reconstruct its component.
        """
        spacer = SgRnaOligos(
            kind="pegrna-spacer",
            spacer=self.spacer,
            top=self.spacer_top,
            bottom=self.spacer_bottom,
            scheme=self.scheme,
        ).reconstruct()
        motif_seq = MOTIF_SEQUENCES[self.motif]
        if not self.ext_top.startswith(_EXT_TOP_OVERHANG):
            raise ValueError("extension oligo missing its 5' overhang")
        body = self.ext_top[len(_EXT_TOP_OVERHANG) :]
        if motif_seq:
            if not body.endswith(motif_seq):
                raise ValueError("extension oligo missing the declared 3' motif")
            body = body[: -len(motif_seq)]
        # Independent RTT/PBS boundary check: the extension body must equal the
        # declared RTT followed by the declared PBS. Comparing the whole body to
        # ``rtt + pbs`` catches a mis-split boundary that a length-based slice
        # (which trusts the stored ``rtt`` length) would silently accept.
        if body != self.rtt + self.pbs:
            raise ValueError("extension oligo does not reconstruct the declared RTT+PBS boundary")
        expected_bottom = _EXT_BOTTOM_OVERHANG + revcomp(self.ext_top[len(_EXT_TOP_OVERHANG) :])
        if self.ext_bottom != expected_bottom:
            raise ValueError("extension antisense oligo is not the reverse complement of the sense")
        return spacer, self.rtt, self.pbs

    @property
    def component_lengths(self) -> dict[str, int]:
        """Return the extension component lengths (RTT, PBS, motif) for audit."""
        return {
            "rtt": len(self.rtt),
            "pbs": len(self.pbs),
            "motif": len(MOTIF_SEQUENCES[self.motif]),
        }


def sgrna_oligos(
    spacer: str, *, scheme: VectorScheme = LENTIGUIDE_BSMBI, kind: str = "sgrna"
) -> SgRnaOligos:
    """Build the annealed oligo duplex for an sgRNA spacer.

    Args:
        spacer: The 5'->3' spacer sequence.
        scheme: The cloning scheme (default: lentiGuide BsmBI).
        kind: A label for the oligo set's chemistry context.

    Returns:
        The :class:`SgRnaOligos` duplex (round-trip validated on construction).
    """
    spacer = _require_dna(spacer, context="sgRNA spacer")
    g = "G" if scheme.prepend_g else ""
    top = scheme.top_overhang + g + spacer
    bottom = scheme.bottom_overhang + revcomp(g + spacer)
    oligos = SgRnaOligos(kind=kind, spacer=spacer, top=top, bottom=bottom, scheme=scheme)
    oligos.reconstruct()  # fail fast on a malformed scheme
    return oligos


def pegrna_oligos(pegrna: PegRNA, *, scheme: VectorScheme = PEGRNA_GG_BSAI) -> PegRNAOligos:
    """Build the annealed oligo duplexes for a pegRNA (spacer + 3' extension).

    Args:
        pegrna: The pegRNA to clone.
        scheme: The cloning scheme (default: pegRNA GG BsaI acceptor).

    Returns:
        The :class:`PegRNAOligos` set (round-trip validated on construction).
    """
    spacer = _require_dna(str(pegrna.spacer.sequence), context="pegRNA spacer")
    rtt = _require_dna(str(pegrna.rtt), context="pegRNA RTT")
    pbs = _require_dna(str(pegrna.pbs), context="pegRNA PBS")
    scaffold = str(pegrna.scaffold)
    if scaffold != SCAFFOLD:
        raise ValueError(
            "pegRNA scaffold does not match the expected SpCas9 sgRNA scaffold constant; "
            "a wrong or empty scaffold would ship a non-functional pegRNA"
        )
    motif_seq = MOTIF_SEQUENCES[pegrna.three_prime_motif]

    g = "G" if scheme.prepend_g else ""
    spacer_top = scheme.top_overhang + g + spacer
    spacer_bottom = scheme.bottom_overhang + revcomp(g + spacer)

    ext_body = rtt + pbs + motif_seq
    ext_top = _EXT_TOP_OVERHANG + ext_body
    ext_bottom = _EXT_BOTTOM_OVERHANG + revcomp(ext_body)

    nicking = None
    if pegrna.nicking_guide is not None:
        nicking = sgrna_oligos(
            str(pegrna.nicking_guide.spacer.sequence), scheme=scheme, kind="ngrna"
        )

    oligos = PegRNAOligos(
        spacer=spacer,
        rtt=rtt,
        pbs=pbs,
        motif=pegrna.three_prime_motif,
        scaffold=str(pegrna.scaffold),
        spacer_top=spacer_top,
        spacer_bottom=spacer_bottom,
        ext_top=ext_top,
        ext_bottom=ext_bottom,
        nicking=nicking,
        scheme=scheme,
    )
    oligos.reconstruct()  # fail fast
    return oligos


def oligos_for(
    candidate: DesignCandidate, *, scheme: VectorScheme | None = None
) -> SgRnaOligos | PegRNAOligos | None:
    """Build the cloning oligos for a candidate, dispatched by chemistry.

    Args:
        candidate: The scored design candidate.
        scheme: Override the cloning scheme; defaults are per-chemistry.

    Returns:
        The oligo set, or ``None`` if the candidate carries no reagent.
    """
    if candidate.pegrna is not None:
        return pegrna_oligos(candidate.pegrna, scheme=scheme or PEGRNA_GG_BSAI)
    if candidate.guide is not None:
        return sgrna_oligos(
            str(candidate.guide.spacer.sequence), scheme=scheme or LENTIGUIDE_BSMBI, kind="sgrna"
        )
    if candidate.base_edit_window is not None:
        return sgrna_oligos(
            str(candidate.base_edit_window.spacer.sequence),
            scheme=scheme or LENTIGUIDE_BSMBI,
            kind="base-editor-sgrna",
        )
    return None
