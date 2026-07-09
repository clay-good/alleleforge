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

#: Type IIS recognition sites for the supported Golden-Gate enzymes (5'->3'). The
#: enzyme cuts **outside** its site, so it must occur exactly once in the acceptor
#: (to excise the stuffer); a copy **inside** the insert means the enzyme also cuts
#: the insert and the clone silently fails — the classic Golden-Gate hazard.
TYPE_IIS_SITES: dict[str, str] = {
    "BsmBI": "CGTCTC",
    "BbsI": "GAAGAC",
    "BsaI": "GGTCTC",
}


def _screen_enzyme_site(insert: str, enzyme: str, *, label: str) -> tuple[str, ...]:
    """Return warning flags for any occurrence of ``enzyme``'s site in ``insert``.

    Screens both strands (the site and its reverse complement) of the variable
    insert an enzyme would see. Each hit yields an ``internal-<enzyme>-site`` flag
    naming the component and the 0-based position, so a cloning-lethal insert is
    surfaced prominently rather than shipping as a clean, round-trip-valid oligo.
    Returns an empty tuple for an unsupported enzyme (no site to screen against).
    """
    site = TYPE_IIS_SITES.get(enzyme)
    if site is None:
        return ()
    seq = insert.upper()
    flags: list[str] = []
    for strand, motif in (("+", site), ("-", revcomp(site))):
        start = seq.find(motif)
        while start != -1:
            flags.append(f"internal-{enzyme}-site:{label}:{strand}@{start}")
            start = seq.find(motif, start + 1)
    return tuple(flags)


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
        prepend_g: Add a 5' ``G`` to the spacer for U6 transcription start (only
            when the spacer does not already begin with ``G``).
        ext_top_overhang: For a pegRNA scheme, the 5' overhang on the sense
            3'-extension oligo (``None`` for an sgRNA-only scheme).
        ext_bottom_overhang: For a pegRNA scheme, the 5' overhang on the antisense
            3'-extension oligo (``None`` for an sgRNA-only scheme).
        phosphorylation: The annealing/ligation prerequisite for this scheme
            (e.g. whether the annealed oligos need 5' phosphorylation with T4 PNK),
            stated in every render so a ligation is not set up that cannot close.
        citation: Protocol citation.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    enzyme: str
    top_overhang: str
    bottom_overhang: str
    prepend_g: bool = True
    ext_top_overhang: str | None = None
    ext_bottom_overhang: str | None = None
    phosphorylation: str | None = None
    citation: str | None = None


#: The annealed-oligo ligation prerequisite shared by the standard Golden-Gate
#: sgRNA/pegRNA protocols: phosphorylate the annealed duplex (T4 PNK) — or order
#: 5'-phosphorylated oligos — and ligate into the enzyme-digested, dephosphorylated
#: vector, so the ligation can close.
_PNK_PHOSPHORYLATION = (
    "Phosphorylate the annealed oligos with T4 PNK (or order 5'-phosphorylated); "
    "ligate into the digested, dephosphorylated vector."
)

#: lentiGuide-Puro / lentiCRISPRv2 sgRNA cloning (BsmBI; CACC / AAAC overhangs).
LENTIGUIDE_BSMBI = VectorScheme(
    name="lentiguide-bsmbi",
    enzyme="BsmBI",
    top_overhang="CACC",
    bottom_overhang="AAAC",
    prepend_g=True,
    phosphorylation=_PNK_PHOSPHORYLATION,
    citation="Sanjana, Shalem & Zhang, Nat Methods 2014 (lentiCRISPRv2/lentiGuide)",
)

#: pX330 / pSpCas9(BB) sgRNA cloning (BbsI; same CACC / AAAC overhangs).
PX330_BBSI = VectorScheme(
    name="px330-bbsi",
    enzyme="BbsI",
    top_overhang="CACC",
    bottom_overhang="AAAC",
    prepend_g=True,
    phosphorylation=_PNK_PHOSPHORYLATION,
    citation="Ran et al., Nat Protoc 2013 (pX330 / pSpCas9(BB))",
)

#: Standard pegRNA Golden-Gate acceptor (BsaI). The spacer duplex uses the U6
#: ``CACC``/``AAAC`` ends; the 3' extension duplex uses a ``GTGC`` sense overhang —
#: the scaffold's own 3' end (``…GGTGC``), which the extension ligates against — and
#: the acceptor's downstream ``AAAA`` overhang on the antisense oligo. Both extension
#: overhangs are named scheme fields (below) so they are cited, not bare constants,
#: and the docstring, constants, and reconstruct check agree on one value.
PEGRNA_GG_BSAI = VectorScheme(
    name="pegrna-gg-bsai",
    enzyme="BsaI",
    top_overhang="CACC",
    bottom_overhang="AAAC",
    prepend_g=True,
    ext_top_overhang="GTGC",
    ext_bottom_overhang="AAAA",
    phosphorylation=_PNK_PHOSPHORYLATION,
    citation="Anzalone et al., Nature 2019 (pU6-pegRNA-GG-acceptor); GTGC = scaffold 3' end",
)


class SgRnaOligos(BaseModel):
    """An annealed sgRNA oligo duplex for one spacer.

    Attributes:
        kind: ``"sgrna"`` (Cas9), ``"base-editor-sgrna"``, or ``"ngrna"``.
        spacer: The intended 5'->3' spacer (the reconstruction target).
        top: The sense oligo to order (5'->3').
        bottom: The antisense oligo to order (5'->3').
        g_added: Whether a 5' U6-start ``G`` was actually prepended (only when the
            scheme asks for it *and* the spacer did not already begin with ``G``).
        warnings: Prominent cloning-hazard flags (e.g. an internal Type IIS
            recognition site), empty when the insert is clean.
        scheme: The cloning scheme used.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    spacer: str
    top: str
    bottom: str
    scheme: VectorScheme
    g_added: bool = False
    warnings: tuple[str, ...] = ()

    def reconstruct(self) -> str:
        """Recover the spacer from the oligos (round-trip check).

        Raises:
            ValueError: If the oligos do not reconstruct a consistent spacer.
        """
        if not self.top.startswith(self.scheme.top_overhang):
            raise ValueError("top oligo missing the scheme's 5' overhang")
        core = self.top[len(self.scheme.top_overhang) :]
        if self.g_added:
            if not core.startswith("G"):
                raise ValueError("top oligo missing the U6 transcription-start G")
            core = core[1:]
        expected_bottom = self.scheme.bottom_overhang + revcomp(
            ("G" if self.g_added else "") + core
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
        g_added: Whether a 5' U6-start ``G`` was prepended to the spacer duplex.
        warnings: Prominent cloning-hazard flags (e.g. an internal Type IIS site in
            the spacer or the 3' extension), empty when both inserts are clean.
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
    g_added: bool = False
    warnings: tuple[str, ...] = ()

    def reconstruct(self) -> tuple[str, str, str]:
        """Recover ``(spacer, rtt, pbs)`` from the oligos (round-trip check).

        Raises:
            ValueError: If any duplex fails to reconstruct its component, or the
                scheme carries no extension overhangs (not a pegRNA scheme).
        """
        spacer = SgRnaOligos(
            kind="pegrna-spacer",
            spacer=self.spacer,
            top=self.spacer_top,
            bottom=self.spacer_bottom,
            scheme=self.scheme,
            g_added=self.g_added,
        ).reconstruct()
        ext_top_overhang, ext_bottom_overhang = _ext_overhangs(self.scheme)
        motif_seq = MOTIF_SEQUENCES[self.motif]
        if not self.ext_top.startswith(ext_top_overhang):
            raise ValueError("extension oligo missing its 5' overhang")
        body = self.ext_top[len(ext_top_overhang) :]
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
        expected_bottom = ext_bottom_overhang + revcomp(self.ext_top[len(ext_top_overhang) :])
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


def _ext_overhangs(scheme: VectorScheme) -> tuple[str, str]:
    """Return the scheme's ``(ext_top, ext_bottom)`` overhangs, or raise.

    A pegRNA scheme must define both 3'-extension overhangs; an sgRNA-only scheme
    leaves them ``None`` and cannot clone a pegRNA extension.
    """
    if scheme.ext_top_overhang is None or scheme.ext_bottom_overhang is None:
        raise ValueError(
            f"scheme {scheme.name!r} defines no pegRNA 3'-extension overhangs; "
            "use a pegRNA scheme (e.g. PEGRNA_GG_BSAI)"
        )
    return scheme.ext_top_overhang, scheme.ext_bottom_overhang


def _prepend_g(spacer: str, scheme: VectorScheme) -> bool:
    """Return whether a 5' U6-start ``G`` should be added for ``spacer``.

    Only when the scheme asks for it *and* the spacer does not already begin with
    ``G`` — adding a second G would ship a 21-nt guide with an unintended 5' base.
    """
    return scheme.prepend_g and not spacer.startswith("G")


def sgrna_oligos(
    spacer: str, *, scheme: VectorScheme = LENTIGUIDE_BSMBI, kind: str = "sgrna"
) -> SgRnaOligos:
    """Build the annealed oligo duplex for an sgRNA spacer.

    The 5' U6-start ``G`` is added only when the spacer does not already begin with
    ``G`` (recorded in ``g_added``), and the assembled top strand (overhang +
    insert) is screened for the scheme enzyme's own recognition site — including
    one straddling the overhang/insert junction — recorded in ``warnings``.

    Args:
        spacer: The 5'->3' spacer sequence.
        scheme: The cloning scheme (default: lentiGuide BsmBI).
        kind: A label for the oligo set's chemistry context.

    Returns:
        The :class:`SgRnaOligos` duplex (round-trip validated on construction).
    """
    spacer = _require_dna(spacer, context="sgRNA spacer")
    g_added = _prepend_g(spacer, scheme)
    g = "G" if g_added else ""
    top = scheme.top_overhang + g + spacer
    bottom = scheme.bottom_overhang + revcomp(g + spacer)
    # Screen the assembled top strand (overhang + insert), not the bare insert: the
    # enzyme site can straddle the overhang/insert junction (e.g. a BsmBI CGTCTC
    # formed by the CACC overhang's trailing C + a spacer beginning GTCTC), which
    # reconstitutes a cloning-lethal internal site the ligated plasmid carries.
    warnings = _screen_enzyme_site(top, scheme.enzyme, label=kind)
    oligos = SgRnaOligos(
        kind=kind, spacer=spacer, top=top, bottom=bottom, scheme=scheme,
        g_added=g_added, warnings=warnings,
    )
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
    ext_top_overhang, ext_bottom_overhang = _ext_overhangs(scheme)

    g_added = _prepend_g(spacer, scheme)
    g = "G" if g_added else ""
    spacer_top = scheme.top_overhang + g + spacer
    spacer_bottom = scheme.bottom_overhang + revcomp(g + spacer)

    ext_body = rtt + pbs + motif_seq
    ext_top = ext_top_overhang + ext_body
    ext_bottom = ext_bottom_overhang + revcomp(ext_body)

    # Screen the assembled top strand of both inserts the enzyme would see — the
    # spacer duplex and the 3' extension (RTT+PBS+motif) — each including its
    # overhang, so a recognition site straddling the overhang/insert junction is
    # caught (it reconstitutes a cloning-lethal internal site in the ligated
    # plasmid), not only a site wholly inside the bare insert body.
    warnings = _screen_enzyme_site(spacer_top, scheme.enzyme, label="pegrna-spacer") + (
        _screen_enzyme_site(ext_top, scheme.enzyme, label="pegrna-extension")
    )

    nicking = None
    if pegrna.nicking_guide is not None:
        nicking = sgrna_oligos(
            str(pegrna.nicking_guide.spacer.sequence), scheme=scheme, kind="ngrna"
        )
    if nicking is not None:
        warnings = warnings + nicking.warnings

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
        g_added=g_added,
        warnings=warnings,
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
