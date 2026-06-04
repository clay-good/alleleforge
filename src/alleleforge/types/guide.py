"""Guide-RNA, base-editing-window, and pegRNA structural models.

These models carry the structural invariants of each reagent class so that
malformed designs are rejected at construction rather than deep in a scoring
loop. Sequences are stored 5'->3' on their own strand; genomic placement is
recorded separately as a :class:`GenomicInterval`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from alleleforge.types.sequence import IUPAC_EXPAND, DNASequence, GenomicInterval

#: Default SpCas9 spacer length (nt).
DEFAULT_SPACER_LENGTH = 20
#: Prime-editing primer-binding-site search range (nt), inclusive.
PBS_RANGE = (8, 17)
#: Prime-editing reverse-transcriptase-template search range (nt), inclusive.
RTT_RANGE = (7, 34)
#: Minimum 3' homology an RTT must place downstream of the edit (nt).
MIN_RTT_3PRIME_HOMOLOGY = 5


class PAM(BaseModel):
    """A protospacer-adjacent motif as an IUPAC pattern (e.g. ``NGG``)."""

    model_config = ConfigDict(frozen=True)

    pattern: str

    @field_validator("pattern")
    @classmethod
    def _validate(cls, value: str) -> str:
        """Upper-case and ensure every character is a known IUPAC code."""
        upper = value.upper()
        bad = [c for c in upper if c not in IUPAC_EXPAND]
        if bad:
            raise ValueError(f"PAM has non-IUPAC characters: {bad}")
        if not upper:
            raise ValueError("PAM pattern is empty")
        return upper

    def __len__(self) -> int:
        """Return the PAM length in bases."""
        return len(self.pattern)

    def matches(self, sequence: str | DNASequence) -> bool:
        """Return ``True`` if ``sequence`` satisfies the IUPAC pattern.

        Args:
            sequence: A concrete sequence the same length as the pattern. Any
                IUPAC ambiguity in the sequence must be a subset of the code it
                is matched against.
        """
        seq = str(sequence).upper()
        if len(seq) != len(self.pattern):
            return False
        for code, base in zip(self.pattern, seq, strict=True):
            allowed = IUPAC_EXPAND[code]
            observed = IUPAC_EXPAND.get(base)
            if observed is None or not observed <= allowed:
                return False
        return True


class Spacer(BaseModel):
    """A guide spacer (protospacer-matching sequence), stored 5'->3'."""

    model_config = ConfigDict(frozen=True)

    sequence: DNASequence

    @field_validator("sequence")
    @classmethod
    def _non_empty(cls, value: DNASequence) -> DNASequence:
        """Reject an empty spacer."""
        if len(value) == 0:
            raise ValueError("spacer is empty")
        return value

    def __len__(self) -> int:
        """Return the spacer length in bases."""
        return len(self.sequence)


class Guide(BaseModel):
    """A placed SpCas9-style guide: spacer + PAM + genomic placement + cut site.

    Attributes:
        spacer: The 5'->3' spacer sequence on its own strand.
        pam: The PAM pattern this guide was enumerated against.
        pam_sequence: The concrete PAM read from the reference.
        placement: The protospacer's genomic interval (strand-aware).
        cut_site: 0-based genomic coordinate of the predicted blunt cut.
    """

    model_config = ConfigDict(frozen=True)

    spacer: Spacer
    pam: PAM
    pam_sequence: DNASequence
    placement: GenomicInterval
    cut_site: int

    @model_validator(mode="after")
    def _check_pam(self) -> Guide:
        """Validate the concrete PAM satisfies the declared pattern."""
        if not self.pam.matches(self.pam_sequence):
            raise ValueError(
                f"PAM sequence {self.pam_sequence} does not match pattern {self.pam.pattern}"
            )
        return self


class BaseEditWindow(BaseModel):
    """A base editor's activity window placed over a protospacer.

    Positions are 1-based within the protospacer, counting from the PAM-distal
    end (position 1) as the base-editing field conventionally does.

    Attributes:
        spacer: The guide spacer.
        editor: The editor name (e.g. ``"ABE8e"``).
        window: The ``(start, end)`` 1-based inclusive activity window.
        target_positions: Protospacer positions intended to be edited.
        bystander_positions: Editable positions outside the intent (bystanders).
        placement: The protospacer's genomic interval (strand-aware), if placed.
        pam: The PAM pattern the spacer was enumerated against, if known.
        pam_sequence: The concrete PAM read from the reference, if known.
    """

    model_config = ConfigDict(frozen=True)

    spacer: Spacer
    editor: str
    window: tuple[int, int]
    target_positions: tuple[int, ...] = ()
    bystander_positions: tuple[int, ...] = ()
    placement: GenomicInterval | None = None
    pam: PAM | None = None
    pam_sequence: DNASequence | None = None

    @model_validator(mode="after")
    def _check_window(self) -> BaseEditWindow:
        """Validate the window is ordered and within the spacer."""
        start, end = self.window
        if start < 1 or end < start:
            raise ValueError(f"invalid window {self.window}")
        if end > len(self.spacer):
            raise ValueError(f"window end {end} exceeds spacer length {len(self.spacer)}")
        return self

    @property
    def has_bystanders(self) -> bool:
        """Return ``True`` if any bystander-editable position is present."""
        return len(self.bystander_positions) > 0

    @property
    def window_bases(self) -> str:
        """Return the in-window base composition (the spacer over the window)."""
        start, end = self.window
        return str(self.spacer.sequence)[start - 1 : end]


class NickingGuide(BaseModel):
    """A prime-editing nicking guide (PE3 / PE3b ngRNA).

    Attributes:
        spacer: The ngRNA spacer.
        placement: The ngRNA protospacer placement.
        nick_offset: Signed distance (nt) from the pegRNA nick to this nick.
        seed_disrupting: ``True`` for a PE3b guide whose nick lies in a
            seed-disrupting position (preferred when available).
    """

    model_config = ConfigDict(frozen=True)

    spacer: Spacer
    placement: GenomicInterval
    nick_offset: int
    seed_disrupting: bool = False


class ThreePrimeMotif(StrEnum):
    """Structured 3' motifs that stabilize an epegRNA."""

    NONE = "none"
    TEVOPREQ1 = "tevopreQ1"
    MPKNOT = "mpknot"


class PegRNA(BaseModel):
    """A prime-editing guide RNA with validated PBS/RTT geometry.

    Attributes:
        spacer: The pegRNA spacer (defines the nick).
        scaffold: The sgRNA scaffold sequence.
        rtt: Reverse-transcriptase template (encodes the edit + 3' homology).
        pbs: Primer-binding site.
        three_prime_motif: Optional structured 3' motif (default tevopreQ1).
        rtt_homology_3prime: Homology length (nt) the RTT places 3' of the edit.
        nicking_guide: Optional PE3/PE3b nicking guide.
        placement: The pegRNA protospacer's genomic interval, if placed.
        nick_site: 0-based genomic coordinate of the pegRNA-induced nick, if placed.
    """

    model_config = ConfigDict(frozen=True)

    spacer: Spacer
    scaffold: DNASequence
    rtt: DNASequence
    pbs: DNASequence
    three_prime_motif: ThreePrimeMotif = ThreePrimeMotif.TEVOPREQ1
    rtt_homology_3prime: int = MIN_RTT_3PRIME_HOMOLOGY
    nicking_guide: NickingGuide | None = None
    placement: GenomicInterval | None = None
    nick_site: int | None = None

    @model_validator(mode="after")
    def _check_geometry(self) -> PegRNA:
        """Validate PBS/RTT lengths and required 3' homology are in range."""
        pbs_len = len(self.pbs)
        if not PBS_RANGE[0] <= pbs_len <= PBS_RANGE[1]:
            raise ValueError(f"PBS length {pbs_len} outside allowed range {PBS_RANGE}")
        rtt_len = len(self.rtt)
        if not RTT_RANGE[0] <= rtt_len <= RTT_RANGE[1]:
            raise ValueError(f"RTT length {rtt_len} outside allowed range {RTT_RANGE}")
        if self.rtt_homology_3prime < MIN_RTT_3PRIME_HOMOLOGY:
            raise ValueError(
                f"RTT 3' homology {self.rtt_homology_3prime} below minimum "
                f"{MIN_RTT_3PRIME_HOMOLOGY}"
            )
        if self.rtt_homology_3prime > rtt_len:
            raise ValueError(
                f"RTT 3' homology {self.rtt_homology_3prime} exceeds RTT length {rtt_len}"
            )
        return self

    @property
    def is_epegrna(self) -> bool:
        """Return ``True`` if a stabilizing 3' motif is attached."""
        return self.three_prime_motif is not ThreePrimeMotif.NONE
