"""Design-candidate and ranked-menu models.

A :class:`DesignCandidate` is one complete, scored option for editing a variant:
a reagent of some chemistry, a calibrated efficiency prediction, a predicted
outcome distribution, and an ancestry-stratified off-target report. The
:class:`RankedMenu` is the ordered set of candidates the Designer returns,
carrying its ranking rationale and full provenance.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from alleleforge.types.edit import Chemistry, EditOutcome
from alleleforge.types.guide import BaseEditWindow, Guide, PegRNA
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.prediction import Prediction
from alleleforge.types.provenance import Provenance


class DesignCandidate(BaseModel):
    """One scored design option for a variant.

    Attributes:
        chemistry: The chemistry this candidate uses.
        guide: The reagent, when it is a Cas9 nuclease guide.
        base_edit_window: The reagent, when it is a base-editor sgRNA + window.
        pegrna: The reagent, when it is a prime-editing pegRNA.
        efficiency: Calibrated on-target efficiency prediction. For base editing
            this carries ``p_intended_exact`` (the probability of the exact
            intended allele), the dimension the chemistry is ranked on.
        bystander_burden: Calibrated expected number of bystander edits, for
            base-editor candidates (``None`` for nuclease / prime candidates).
        outcome: Predicted edit-outcome distribution.
        offtarget: Ancestry-stratified off-target report.
        flags: Free-form annotations (e.g. ``"ood"``, ``"bystander-risk"``).
        rationale: Human-readable note on this candidate's standing.
    """

    model_config = ConfigDict(frozen=True)

    chemistry: Chemistry
    guide: Guide | None = None
    base_edit_window: BaseEditWindow | None = None
    pegrna: PegRNA | None = None
    efficiency: Prediction[float] | None = None
    bystander_burden: Prediction[float] | None = None
    outcome: EditOutcome | None = None
    offtarget: OffTargetReport | None = None
    flags: tuple[str, ...] = ()
    rationale: str | None = None

    @property
    def has_reagent(self) -> bool:
        """Return ``True`` if a guide, base-edit window, or pegRNA is attached."""
        return (
            self.guide is not None or self.base_edit_window is not None or self.pegrna is not None
        )


class RankedMenu(BaseModel):
    """An ordered menu of design candidates with rationale and provenance.

    Attributes:
        candidates: Candidates in rank order (best first).
        rationale: How the ranking was computed and what drove the order.
        pareto_front: Indices into ``candidates`` that are Pareto-optimal.
        provenance: The reproducibility block for this menu.
    """

    model_config = ConfigDict(frozen=True)

    candidates: tuple[DesignCandidate, ...]
    rationale: str | None = None
    pareto_front: tuple[int, ...] = ()
    provenance: Provenance | None = None

    @property
    def best(self) -> DesignCandidate | None:
        """Return the top-ranked candidate, or ``None`` for an empty menu."""
        return self.candidates[0] if self.candidates else None
