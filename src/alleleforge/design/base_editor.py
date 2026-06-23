"""The base-editing design vertical: variant to ranked DesignCandidates.

:func:`design_base_editor` realizes the ABE/CBE slice — **enumerate -> window
outcome -> off-target -> candidate** — and ranks the editor/guide combinations by
the spec's objective: maximize the probability of the **exact** intended allele
while minimizing **bystander** burden, surfacing that tradeoff on every candidate.
The cleanest combination is flagged as the recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype
from alleleforge.enumerate.base_editor import BASE_EDITORS, BaseEditor, enumerate_base_edits
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search as offtarget_search
from alleleforge.scoring.base_outcome import (
    BaseEditOutcomePredictor,
    WindowOutcome,
    recommend_window,
)
from alleleforge.types.candidate import DesignCandidate
from alleleforge.types.edit import EditIntent
from alleleforge.types.guide import BaseEditWindow
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.provenance import ModelCheckpoint
from alleleforge.types.sequence import GenomicInterval
from alleleforge.variant.resolver import ResolvedVariant


def _flags(
    window: BaseEditWindow, outcome: WindowOutcome, offreport: OffTargetReport | None
) -> tuple[str, ...]:
    """Return free-form annotations surfacing the bystander tradeoff."""
    flags: list[str] = []
    if window.has_bystanders:
        flags.append(f"bystander-present:{len(window.bystander_positions)}")
    else:
        flags.append("clean")
    flags.append(f"bystander-burden:{outcome.bystander_burden.value:.2f}")
    if offreport is not None and offreport.population_sites:
        flags.append("population-offtarget")
    return tuple(flags)


def base_editor_model_checkpoints() -> tuple[ModelCheckpoint, ...]:
    """Return the provenance checkpoint for the default base-edit outcome model.

    The default window-outcome predictor is the BE-DICT baseline (``be-dict``),
    which carries a model card stamped into a menu's provenance whenever the
    base-editing vertical runs.
    """
    return (BaseEditOutcomePredictor().model_card().to_checkpoint(),)


class BaseOutcomePredictor(Protocol):
    """Structural type a base-edit window-outcome predictor must satisfy.

    Both the weight-free :class:`BaseEditOutcomePredictor` baseline and the trained
    :class:`~alleleforge.scoring.base_outcome.BeDictAdapter` satisfy it.
    """

    name: str

    def predict(self, window: BaseEditWindow, editor: BaseEditor) -> WindowOutcome:
        """Return the predicted window outcome for ``window`` under ``editor``."""
        ...


def design_base_editor(
    resolved: ResolvedVariant,
    intent: EditIntent = EditIntent.CORRECT,
    *,
    reference: ReferenceGenome,
    editors: tuple[BaseEditor, ...] = BASE_EDITORS,
    outcome_predictor: BaseOutcomePredictor | None = None,
    gnomad: GnomadDB | None = None,
    haplotypes: Iterable[Haplotype] = (),
    patient_vcf: Iterable[object] | None = None,
    populations: Sequence[str] | None = None,
    offtarget_regions: Sequence[GenomicInterval] | None = None,
    run_offtarget: bool = True,
    max_candidates: int | None = None,
) -> list[DesignCandidate]:
    """Design base-editor candidates for a resolved variant.

    Args:
        resolved: The resolved variant (must be a transition SNV to be editable).
        intent: What the edit must accomplish (sets the required transition).
        reference: The reference genome.
        editors: Editors to consider (default: ABE8e, CBE4max, evoCDA1).
        outcome_predictor: Window-outcome predictor (default: the BE-DICT baseline).
        gnomad: gnomAD DB for population-aware off-target (optional).
        haplotypes: Common haplotypes for haplotype-aware off-target (optional).
        patient_vcf: Personal variants for off-target personalization (optional).
        populations: Ancestry labels to query/stratify.
        offtarget_regions: Restrict the off-target search (default: every contig).
        run_offtarget: Run the off-target engine (set ``False`` to skip it).
        max_candidates: Cap the number of returned candidates.

    Returns:
        Candidates ranked by descending exact-intended probability then ascending
        bystander burden; the top (cleanest) candidate is flagged ``recommended``.
    """
    windows = enumerate_base_edits(resolved, reference=reference, intent=intent, editors=editors)
    predictor = outcome_predictor or BaseEditOutcomePredictor()
    by_name = {e.name: e for e in editors}

    built: list[tuple[DesignCandidate, WindowOutcome]] = []
    for window in windows:
        editor = by_name[window.editor]
        outcome = predictor.predict(window, editor)
        offreport: OffTargetReport | None = None
        if run_offtarget and window.pam is not None:
            offreport = offtarget_search(
                window.spacer,
                window.pam,
                reference=reference,
                gnomad=gnomad,
                haplotypes=haplotypes,
                patient_vcf=patient_vcf,  # type: ignore[arg-type]  # Variant iterable
                populations=populations,
                regions=offtarget_regions,
            )
        candidate = DesignCandidate(
            chemistry=editor.chemistry,
            base_edit_window=window,
            efficiency=outcome.p_intended_exact,  # ranked on clean-edit probability
            bystander_burden=outcome.bystander_burden,
            outcome=outcome.outcome,
            offtarget=offreport,
            flags=_flags(window, outcome, offreport),
            rationale=(
                f"{editor.name} sgRNA on "
                f"{window.placement.strand.value if window.placement else '?'} strand; "
                f"P(exact)={outcome.p_intended_exact.value:.2f}, "
                f"bystander burden={outcome.bystander_burden.value:.2f}"
            ),
        )
        built.append((candidate, outcome))

    built.sort(key=lambda cw: (-cw[1].p_intended_exact.value, cw[1].bystander_burden.value))
    candidates = [c for c, _ in built]
    if candidates:
        best = recommend_window([(c.base_edit_window, o) for c, o in built if c.base_edit_window])
        if best is not None:
            top = candidates[0]
            candidates[0] = top.model_copy(update={"flags": (*top.flags, "recommended")})
    return candidates[:max_candidates] if max_candidates is not None else candidates
