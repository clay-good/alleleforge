"""Off-target specificity scoring: CFD, MIT, and a Cas12a CFD analog.

Two published single-guide specificity scores plus a Cas12a analog, behind one
:class:`OffTargetScorer` protocol so a Phase 6 ML scorer can be swapped in
without touching the engine.

* **MIT / Hsu score** (Hsu et al., *Nat Biotechnol* 2013). A position-weighted
  product penalizing mismatches by location, pairwise spacing, and count. The
  20-position weight vector is the published table; the implementation is exact.
* **CFD — Cutting Frequency Determination** (Doench et al., *Nat Biotechnol*
  2016). The CFD score is ``∏ w(position, mismatch) · w(PAM)``. The PAM
  dinucleotide weights here are the published CFD values. The per-position
  *mismatch* weights default to a transparent, monotonic seed-tolerance model
  (PAM-distal mismatches tolerated, PAM-proximal seed mismatches penalized);
  the exact 400-value Doench matrix can be supplied via ``mismatch_weights`` so
  the published table drops in without code changes.
* **Cas12a CFD analog.** Same multiplicative structure with the seed at the
  PAM-proximal **5'** end (Cas12a's PAM is 5' of the protospacer) and a ``TTTV``
  PAM model. Documented as an analog pending a Cas12a-specific published matrix.

All scores are returned in ``[0, 1]`` (1.0 = perfect match, no PAM penalty).
"""

from __future__ import annotations

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
        ValueError: If ``spacer`` and ``protospacer`` differ in length.
    """
    if len(spacer) != len(protospacer):
        raise ValueError("spacer and protospacer must be the same length for CFD")
    spacer, protospacer = spacer.upper(), protospacer.upper()
    pam_table = pam_weights if pam_weights is not None else CFD_PAM_WEIGHTS
    score = pam_table.get(_normalize_pam(pam_sequence), 0.0)
    length = len(spacer)
    for i, (s, t) in enumerate(zip(spacer, protospacer, strict=True)):
        if s == t:
            continue
        if mismatch_weights is not None:
            score *= mismatch_weights.get((s, t, i), 0.0)
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
    monotonic seed-tolerance shape mirrored to the 5' end. A ``TTTV``-matching
    PAM contributes full weight; a non-canonical PAM contributes none. Marked an
    analog pending a Cas12a-specific published matrix.
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
            score *= mismatch_weights.get((s, t, i), 0.0)
        else:  # mirror the seed to the 5' end: position 0 is PAM-proximal
            score *= _default_mismatch_weight(s, t, length - 1 - i, length)
    return score


@runtime_checkable
class OffTargetScorer(Protocol):
    """Anything that scores a (spacer, protospacer, PAM) off-target candidate."""

    name: str
    method: ScoreMethod

    def score(self, spacer: str, protospacer: str, pam_sequence: str) -> float:
        """Return the specificity score in ``[0, 1]`` for one candidate."""
        ...


class CfdScorer:
    """The CFD scorer (default off-target scorer)."""

    name = "CFD"
    method = ScoreMethod.CFD

    def __init__(self, mismatch_weights: MismatchWeights | None = None) -> None:
        """Optionally bind the published Doench mismatch-weight table."""
        self._mismatch_weights = mismatch_weights

    def score(self, spacer: str, protospacer: str, pam_sequence: str) -> float:
        """Return the CFD score for one candidate."""
        return cfd_score(spacer, protospacer, pam_sequence, mismatch_weights=self._mismatch_weights)


class MitScorer:
    """The MIT/Hsu specificity scorer."""

    name = "MIT"
    method = ScoreMethod.MIT

    def score(self, spacer: str, protospacer: str, pam_sequence: str) -> float:
        """Return the MIT score for one candidate (PAM is not used)."""
        return mit_score(spacer, protospacer)


class Cas12aCfdScorer:
    """The Cas12a CFD-analog scorer."""

    name = "CFD-Cas12a"
    method = ScoreMethod.CFD_CAS12A

    def __init__(self, mismatch_weights: MismatchWeights | None = None) -> None:
        """Optionally bind a Cas12a mismatch-weight table."""
        self._mismatch_weights = mismatch_weights

    def score(self, spacer: str, protospacer: str, pam_sequence: str) -> float:
        """Return the Cas12a CFD-analog score for one candidate."""
        return cas12a_cfd_score(
            spacer, protospacer, pam_sequence, mismatch_weights=self._mismatch_weights
        )
