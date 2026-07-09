"""Off-target specificity scoring: CFD, MIT, and a Cas12a CFD analog.

Two published single-guide specificity scores plus a Cas12a analog, behind one
:class:`OffTargetScorer` protocol so a Phase 6 ML scorer can be swapped in
without touching the engine.

* **MIT / Hsu score** (Hsu et al., *Nat Biotechnol* 2013). A position-weighted
  product penalizing mismatches by location, pairwise spacing, and count. The
  20-position weight vector is the published table; the implementation is exact.
* **CFD — Cutting Frequency Determination** (Doench et al., *Nat Biotechnol*
  2016). The CFD score is ``∏ w(position, mismatch) · w(PAM)``. Both the PAM
  dinucleotide weights and the per-position *mismatch* weights default to the
  **published Doench 2016 matrix** (vendored in ``cfd_matrix.json`` and
  cross-verified byte-for-byte against CRISPOR and CRISPRitz), so a default score
  is the CFD number a reviewer expects. A transparent, monotonic seed-tolerance
  approximation (PAM-distal mismatches tolerated, PAM-proximal seed mismatches
  penalized) remains available via ``CfdScorer(approximate=True)``, and a custom
  table can be injected via ``mismatch_weights``.
* **Cas12a CFD analog.** Same multiplicative structure with the seed at the
  PAM-proximal **5'** end (Cas12a's PAM is 5' of the protospacer) and a ``TTTV``
  PAM model. Documented as an analog pending a Cas12a-specific published matrix.

All scores are returned in ``[0, 1]`` (1.0 = perfect match, no PAM penalty).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable

from alleleforge.types.offtarget import ScoreMethod

#: Hsu 2013 position weights for a 20-nt spacer, 5'->3' (index 0 = PAM-distal,
#: index 19 = PAM-proximal). Larger weight => a mismatch there hurts more.
MIT_WEIGHTS: tuple[float, ...] = (
    0.0,
    0.0,
    0.014,
    0.0,
    0.0,
    0.395,
    0.317,
    0.0,
    0.389,
    0.079,
    0.445,
    0.508,
    0.613,
    0.851,
    0.732,
    0.828,
    0.615,
    0.804,
    0.685,
    0.583,
)

#: Published CFD PAM dinucleotide weights (the two nt 3' of the ``N`` in ``NGG``).
#: ``GG`` = 1.0 (canonical); ``AG``/``CG``/``GA``/``GC``/``GT``/``TG`` carry the
#: low-stringency residual activity reported by Doench 2016; the rest are 0.
CFD_PAM_WEIGHTS: dict[str, float] = {
    "AA": 0.0,
    "AC": 0.0,
    "AG": 0.259259259,
    "AT": 0.0,
    "CA": 0.0,
    "CC": 0.0,
    "CG": 0.107142857,
    "CT": 0.0,
    "GA": 0.069444444,
    "GC": 0.022222222,
    "GG": 1.0,
    "GT": 0.016129032,
    "TA": 0.0,
    "TC": 0.0,
    "TG": 0.038961039,
    "TT": 0.0,
}

#: A mismatch-weight table maps ``(spacer_base, target_base, position)`` to the
#: retained activity (``1.0`` = no effect). Used to override the default model
#: with the published Doench matrix.
MismatchWeights = dict[tuple[str, str, int], float]

#: The vendored, cross-verified Doench 2016 CFD weight matrix (see its own
#: ``_provenance`` block for the two-source authenticity record).
CFD_MATRIX_FILE = Path(__file__).parent / "cfd_matrix.json"

#: Matrix-identity labels recorded on a score so a consumer can tell published-CFD
#: from the transparent fallback without inspecting the number.
PUBLISHED_CFD_MATRIX_ID = "doench-2016-cfd"
APPROX_CFD_MATRIX_ID = "doench-2016-seed-tolerance-approximation"

#: The spacer length the published Doench 2016 CFD matrix is defined for. Its
#: per-position weights are indexed by absolute position 0–19; an alignment of any
#: other length falls outside the matrix (a mismatch at position ≥ 20 has no
#: published weight and silently collapses CFD to 0), so a fixed-position matrix is
#: only honestly applied at exactly this length.
CFD_SPACER_LENGTH = 20


@lru_cache(maxsize=1)
def published_cfd_mismatch_weights() -> MismatchWeights:
    """Return the published Doench 2016 CFD mismatch matrix as a scorer table.

    Loads the vendored :data:`CFD_MATRIX_FILE` and converts each upstream
    ``r<guide>:d<complement-of-target>,<1-based-pos>`` entry into this scorer's
    ``(spacer_base, target_base, 0-based-pos)`` key. The guide RNA base maps to DNA
    (``U``→``T``) and the target base is the complement of the stored ``d`` base, so
    the table reproduces the reference CFD calculator exactly. Cached: the file is
    read and converted once.
    """
    doc = json.loads(CFD_MATRIX_FILE.read_text())
    complement = {"A": "T", "T": "A", "C": "G", "G": "C"}
    table: MismatchWeights = {}
    for key, weight in doc["mismatch"].items():
        rpart, pos = key.split(",")  # e.g. "rU:dT", "12"
        guide_rna, target_d = rpart[1], rpart[4]
        spacer_dna = "T" if guide_rna == "U" else guide_rna
        table[(spacer_dna, complement[target_d], int(pos) - 1)] = weight
    return table


def _checked_weight(weight: float, *, context: str) -> float:
    """Return ``weight`` if it is a valid retained-activity in ``[0, 1]``.

    A CFD/analog weight is a retained-activity fraction, so it must lie in
    ``[0, 1]``. A supplied table with an out-of-range value would otherwise drive
    a specificity score outside ``[0, 1]`` that only fails later, in the
    :class:`~alleleforge.types.offtarget.OffTargetSite` validator. Catching it
    here names the offending weight at scoring time.

    Raises:
        ValueError: If ``weight`` is outside ``[0, 1]``.
    """
    if not 0.0 <= weight <= 1.0:
        raise ValueError(f"{context} weight {weight} is outside [0, 1]")
    return weight


def _default_mismatch_weight(
    spacer_base: str, target_base: str, position: int, length: int
) -> float:
    """Return the default retained-activity weight for one mismatch.

    A transparent, monotonic approximation of CFD's empirically-established
    structure: a mismatch at the PAM-distal end (``position`` 0) is largely
    tolerated, while one in the PAM-proximal seed sharply reduces activity. A
    small transition/transversion adjustment reflects that transitions (purine
    <-> purine, pyrimidine <-> pyrimidine) are better tolerated than
    transversions. This default is replaced wholesale when the published
    ``mismatch_weights`` table is supplied.
    """
    pam_proximity = position / (length - 1) if length > 1 else 1.0  # 0 distal -> 1 proximal
    tolerated = 0.95 * (1.0 - pam_proximity) + 0.05  # ~0.95 distal -> ~0.05 seed
    transitions = {frozenset("AG"), frozenset("CT")}
    if frozenset((spacer_base, target_base)) in transitions:
        tolerated = min(1.0, tolerated * 1.15)
    return tolerated


def _normalize_pam(pam_sequence: str) -> str:
    """Return the two PAM-defining nucleotides (the ``GG`` of ``NGG``)."""
    pam = pam_sequence.upper()
    return pam[-2:] if len(pam) >= 2 else pam


def cfd_score(
    spacer: str,
    protospacer: str,
    pam_sequence: str,
    *,
    mismatch_weights: MismatchWeights | None = None,
    pam_weights: dict[str, float] | None = None,
) -> float:
    """Return the CFD specificity score for one spacer/protospacer/PAM.

    Args:
        spacer: The guide spacer (RNA), 5'->3'.
        protospacer: The genomic target, 5'->3', the same length as ``spacer``.
        pam_sequence: The concrete PAM read from the genome (e.g. ``"TGG"``).
        mismatch_weights: Optional published ``(spacer, target, pos) -> weight``
            table; the transparent default model is used when omitted.
        pam_weights: Optional PAM dinucleotide weights; defaults to
            :data:`CFD_PAM_WEIGHTS`.

    Returns:
        The CFD score in ``[0, 1]``.

    Raises:
        ValueError: If ``spacer`` and ``protospacer`` differ in length, or if a
            fixed-position ``mismatch_weights`` matrix is supplied for anything
            other than a 20-nt alignment (its weights are indexed by absolute
            position 0–19, so an off-length input is scored in the wrong register
            or silently collapses — see :data:`CFD_SPACER_LENGTH`).
    """
    if len(spacer) != len(protospacer):
        raise ValueError("spacer and protospacer must be the same length for CFD")
    if mismatch_weights is not None and len(spacer) != CFD_SPACER_LENGTH:
        raise ValueError(
            f"published CFD matrix requires a {CFD_SPACER_LENGTH}-nt spacer/protospacer, "
            f"got {len(spacer)} nt (its weights are defined only for positions 0-19)"
        )
    spacer, protospacer = spacer.upper(), protospacer.upper()
    pam_table = pam_weights if pam_weights is not None else CFD_PAM_WEIGHTS
    score = _checked_weight(pam_table.get(_normalize_pam(pam_sequence), 0.0), context="CFD PAM")
    length = len(spacer)
    for i, (s, t) in enumerate(zip(spacer, protospacer, strict=True)):
        if s == t:
            continue
        if mismatch_weights is not None:
            score *= _checked_weight(
                mismatch_weights.get((s, t, i), 0.0), context=f"CFD mismatch ({s}->{t} @ {i})"
            )
        else:
            score *= _default_mismatch_weight(s, t, i, length)
    return score


def mit_score(spacer: str, protospacer: str) -> float:
    """Return the MIT/Hsu single-site specificity score in ``[0, 1]``.

    Implements the Hsu 2013 formula: the product of per-mismatch position
    weights, a pairwise-spacing term, and an inverse-square mismatch-count term.

    Args:
        spacer: The guide spacer, 5'->3'.
        protospacer: The genomic target, 5'->3', the same length as ``spacer``.

    Returns:
        The MIT score in ``[0, 1]`` (1.0 for a perfect match).

    Raises:
        ValueError: If the two sequences differ in length, or are not 20 nt.
    """
    if len(spacer) != len(protospacer):
        raise ValueError("spacer and protospacer must be the same length for MIT")
    if len(spacer) != len(MIT_WEIGHTS):
        raise ValueError(f"MIT score requires {len(MIT_WEIGHTS)}-nt spacers")
    spacer, protospacer = spacer.upper(), protospacer.upper()
    mm_positions = [i for i, (s, t) in enumerate(zip(spacer, protospacer, strict=True)) if s != t]
    if not mm_positions:
        return 1.0
    score = 1.0
    for pos in mm_positions:
        score *= 1.0 - MIT_WEIGHTS[pos]
    n_mm = len(mm_positions)
    if n_mm > 1:
        mean_gap = (mm_positions[-1] - mm_positions[0]) / (n_mm - 1)
        score *= 1.0 / (((len(spacer) - 1 - mean_gap) / (len(spacer) - 1)) * 4 + 1)
    score *= 1.0 / (n_mm**2)
    return score


def cas12a_cfd_score(
    spacer: str,
    protospacer: str,
    pam_sequence: str,
    *,
    mismatch_weights: MismatchWeights | None = None,
) -> float:
    """Return a Cas12a CFD-analog score in ``[0, 1]``.

    Cas12a recognizes a 5' ``TTTV`` PAM, so its seed lies at the PAM-proximal
    **5'** end of the protospacer. The default mismatch model is the same
    monotonic seed-tolerance shape mirrored to the 5' end. A ``TTTV``-matching PAM
    contributes full weight; a non-canonical PAM contributes a small residual
    weight (0.05) rather than zero, so a mismatch-free non-``TTTV`` site still
    surfaces for review instead of being silently dropped below threshold. Marked
    an analog pending a Cas12a-specific published matrix.
    """
    if len(spacer) != len(protospacer):
        raise ValueError("spacer and protospacer must be the same length")
    spacer, protospacer = spacer.upper(), protospacer.upper()
    pam = pam_sequence.upper()
    pam_ok = len(pam) >= 4 and pam[:3] == "TTT" and pam[3] in "ACG"  # TTTV
    score = 1.0 if pam_ok else 0.05
    length = len(spacer)
    for i, (s, t) in enumerate(zip(spacer, protospacer, strict=True)):
        if s == t:
            continue
        if mismatch_weights is not None:
            score *= _checked_weight(
                mismatch_weights.get((s, t, i), 0.0),
                context=f"Cas12a CFD mismatch ({s}->{t} @ {i})",
            )
        else:  # mirror the seed to the 5' end: position 0 is PAM-proximal
            score *= _default_mismatch_weight(s, t, length - 1 - i, length)
    return score


@runtime_checkable
class OffTargetScorer(Protocol):
    """Anything that scores a (spacer, protospacer, PAM) off-target candidate."""

    name: str
    method: ScoreMethod
    #: A human-readable identity of the weight source (which matrix/table produced
    #: the scores), recorded in the report so a consumer can tell whether they are
    #: reading published-CFD or an approximation, not just a bare number.
    matrix: str

    def score(
        self, spacer: str, protospacer: str, pam_sequence: str, *, bulged: bool = False
    ) -> float:
        """Return the specificity score in ``[0, 1]`` for one candidate.

        ``bulged`` marks a bulge-collapsed alignment (the engine sets it from the
        hit's bulge counts), so a fixed-matrix scorer can fall back off a table it
        cannot apply off-register even when both strings remain 20 nt.
        """
        ...


class CfdScorer:
    """The CFD scorer (default off-target scorer).

    By default this uses the **published Doench 2016 CFD matrix** (vendored and
    cross-verified against two independent tools), so out-of-the-box scores are the
    CFD numbers a reviewer expects. Pass ``approximate=True`` for the transparent
    seed-tolerance fallback (deterministic, no data file), or inject a custom
    ``mismatch_weights`` table. Whichever is used is recorded in :attr:`matrix`.
    """

    name = "CFD"
    method = ScoreMethod.CFD
    #: The published-matrix identity recorded on a default score.
    PUBLISHED_MATRIX = PUBLISHED_CFD_MATRIX_ID
    #: The transparent-fallback identity, named honestly so an approximate score is
    #: never mistaken for published CFD.
    APPROXIMATE_MATRIX = APPROX_CFD_MATRIX_ID

    def __init__(
        self,
        mismatch_weights: MismatchWeights | None = None,
        *,
        matrix: str | None = None,
        approximate: bool = False,
    ) -> None:
        """Bind the CFD mismatch-weight table.

        Args:
            mismatch_weights: A custom ``(spacer, target, pos) -> weight`` table. When
                omitted, the published Doench 2016 matrix is used unless
                ``approximate`` is set.
            matrix: Override the recorded matrix-identity label.
            approximate: Use the transparent seed-tolerance approximation instead of
                the published matrix (ignored when ``mismatch_weights`` is given).
        """
        if mismatch_weights is not None:
            self._mismatch_weights: MismatchWeights | None = mismatch_weights
            self.matrix = matrix or "custom-mismatch-matrix"
        elif approximate:
            self._mismatch_weights = None
            self.matrix = matrix or self.APPROXIMATE_MATRIX
        else:
            self._mismatch_weights = published_cfd_mismatch_weights()
            self.matrix = matrix or self.PUBLISHED_MATRIX

    def _uses_fallback(self, spacer: str, bulged: bool) -> bool:
        """Return whether this call must fall back off the fixed published matrix.

        A fixed-position matrix (published or custom) is defined only at
        :data:`CFD_SPACER_LENGTH` and only for an **ungapped** alignment. For a
        bulge-collapsed or off-length alignment it cannot be applied honestly, so
        the scorer falls back to the length-relative approximation for that one
        call. A DNA bulge collapses the *target* but leaves both strings at 20 nt,
        so the length check alone would not catch it — ``bulged`` (set by the engine
        from the hit's bulge counts) closes that hole. The approximation matrix (no
        fixed table) is length-agnostic and never needs a fallback.
        """
        return self._mismatch_weights is not None and (bulged or len(spacer) != CFD_SPACER_LENGTH)

    def score(
        self, spacer: str, protospacer: str, pam_sequence: str, *, bulged: bool = False
    ) -> float:
        """Return the CFD score for one candidate.

        When a fixed published/custom matrix is bound but the alignment is
        bulge-collapsed (``bulged``) or not :data:`CFD_SPACER_LENGTH`, the
        length-relative approximation is used instead of scoring off-register; the
        effective matrix for that call is reported by :meth:`matrix_for`.
        """
        weights = None if self._uses_fallback(spacer, bulged) else self._mismatch_weights
        return cfd_score(spacer, protospacer, pam_sequence, mismatch_weights=weights)

    def matrix_for(self, spacer: str, protospacer: str, *, bulged: bool = False) -> str:
        """Return the matrix identity that :meth:`score` uses for this alignment.

        Equals :attr:`matrix` for an ungapped, in-length alignment; for a fallback
        call (bulge-collapsed via ``bulged``, or off-length under a fixed matrix) it
        returns the approximation identity, so a bulged/off-length score is never
        labeled published CFD.
        """
        return self.APPROXIMATE_MATRIX if self._uses_fallback(spacer, bulged) else self.matrix


class MitScorer:
    """The MIT/Hsu specificity scorer."""

    name = "MIT"
    method = ScoreMethod.MIT
    matrix = "hsu-2013-position-weights"

    def score(
        self, spacer: str, protospacer: str, pam_sequence: str, *, bulged: bool = False
    ) -> float:
        """Return the MIT score for one candidate (PAM and ``bulged`` are not used).

        The MIT score is only reported for an ungapped 20-nt alignment (the engine
        gates that separately), so the bulge flag does not change this computation.
        """
        return mit_score(spacer, protospacer)


class Cas12aCfdScorer:
    """The Cas12a CFD-analog scorer."""

    name = "CFD-Cas12a"
    method = ScoreMethod.CFD_CAS12A
    #: The Cas12a analog is documented as *unvalidated* pending a Cas12a-specific
    #: published matrix; the label carries that caveat into the report so the score
    #: is not mistaken for a validated Cas12a risk signal.
    DEFAULT_MATRIX = "cas12a-analog-approximation (unvalidated)"

    def __init__(
        self, mismatch_weights: MismatchWeights | None = None, *, matrix: str | None = None
    ) -> None:
        """Optionally bind a Cas12a mismatch-weight table."""
        self._mismatch_weights = mismatch_weights
        if matrix is not None:
            self.matrix = matrix
        elif mismatch_weights is None:
            self.matrix = self.DEFAULT_MATRIX
        else:
            self.matrix = "custom-mismatch-matrix (unvalidated cas12a analog)"

    def score(
        self, spacer: str, protospacer: str, pam_sequence: str, *, bulged: bool = False
    ) -> float:
        """Return the Cas12a CFD-analog score for one candidate.

        The analog is length-relative (no fixed table), so ``bulged`` does not
        change the computation; the parameter is accepted for interface parity.
        """
        return cas12a_cfd_score(
            spacer, protospacer, pam_sequence, mismatch_weights=self._mismatch_weights
        )
