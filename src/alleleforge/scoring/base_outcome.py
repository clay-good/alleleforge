"""Base-editing window-outcome prediction.

The hard part of base editing is the *window outcome*: of the editable bases in
the activity window, which get edited, and what bystanders ride along. This
module predicts the distribution over window alleles and derives two calibrated
quantities the designer ranks on:

* ``p_intended_exact`` — the probability of the **exact** intended allele (the
  target base edited and **no** bystander edited).
* ``bystander_burden`` — the expected number of bystander edits.

The default is a transparent, deterministic baseline: each editable base in the
window is edited with a probability that peaks mid-window and is modulated by the
deaminase's motif preference (e.g. APOBEC1's TC motif); positions are treated as
independent, and the 2^k window alleles are enumerated. The trained BE-DICT
(default) and BE-Hive models load through the license-gated model zoo when
present; an ensemble mode reports their top-allele agreement.
"""

from __future__ import annotations

import contextlib
import itertools
import os
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alleleforge.enumerate.base_editor import BaseEditor
from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import (
    Downloader,
    ModelCard,
    ModelRegistry,
    ModelUse,
    default_registry,
)
from alleleforge.types.edit import AlleleOutcome, EditOutcome
from alleleforge.types.guide import BaseEditWindow
from alleleforge.types.prediction import Prediction, UncertaintyMethod

#: Baseline peak per-base editing probability at the window center.
_PEAK_EDIT = 0.6

#: Heuristic interval half-width for the baseline's calibrated predictions.
_INTERVAL_HALF = 0.15


@dataclass(frozen=True)
class WindowOutcome:
    """A predicted base-edit window outcome with its derived quantities."""

    outcome: EditOutcome
    p_intended_exact: Prediction[float]
    bystander_burden: Prediction[float]


def _position_efficiency(position: int, window: tuple[int, int]) -> float:
    """Return a 0-1 position weight peaking at the window center."""
    lo, hi = window
    center = (lo + hi) / 2.0
    half = max(1.0, (hi - lo) / 2.0)
    return max(0.1, 1.0 - abs(position - center) / (half + 1.0))


def _edit_probability(
    position: int, spacer: str, editor: BaseEditor, window: tuple[int, int]
) -> float:
    """Return the probability the base at ``position`` is edited."""
    prob = _PEAK_EDIT * _position_efficiency(position, window)
    if editor.motif_preference is not None and position >= 2:
        neighbor = spacer[position - 2]  # the 5' neighbor of the editable base
        prob *= 1.3 if neighbor == editor.motif_preference else 0.5
    return min(0.99, max(0.0, prob))


def _allele(edited: frozenset[int], editor: BaseEditor) -> str:
    """Return an allele descriptor for an edited-position set."""
    if not edited:
        return "wildtype"
    return ";".join(f"{editor.target_base}{p}{editor.result_base}" for p in sorted(edited))


class BaseEditOutcomePredictor:
    """A transparent window-outcome baseline (the BE-DICT mechanism)."""

    name = "be-dict-baseline"

    def __init__(self, *, registry: ModelRegistry | None = None) -> None:
        """Configure the (optional) model-card registry."""
        self._registry = registry or default_registry()

    def model_card(self) -> ModelCard:
        """Return the BE-DICT model card (mechanism this baseline mirrors)."""
        return self._registry.get("be-dict")

    def predict(self, window: BaseEditWindow, editor: BaseEditor) -> WindowOutcome:
        """Predict the window-outcome distribution and derived quantities.

        Args:
            window: The placed base-edit window (target + bystander positions).
            editor: The base editor (provides the motif preference and bases).

        Returns:
            A :class:`WindowOutcome` with the allele distribution,
            ``p_intended_exact``, and ``bystander_burden``.
        """
        spacer = str(window.spacer.sequence)
        editable = sorted({*window.target_positions, *window.bystander_positions})
        probs = {p: _edit_probability(p, spacer, editor, window.window) for p in editable}
        return _assemble_window_outcome(window, editor, probs)


def _assemble_window_outcome(
    window: BaseEditWindow, editor: BaseEditor, probs: dict[int, float]
) -> WindowOutcome:
    """Build a :class:`WindowOutcome` from per-position edit probabilities.

    ``probs`` maps each editable **1-based** protospacer position to its edit
    probability. Positions are treated as independent and the 2^k window alleles
    are enumerated. Shared by the heuristic baseline and the trained adapters so
    the allele math is identical regardless of where the probabilities come from.
    """
    editable = sorted(probs)
    alleles: list[AlleleOutcome] = []
    intended = frozenset(window.target_positions)
    for r in range(len(editable) + 1):
        for subset in itertools.combinations(editable, r):
            s = frozenset(subset)
            prob = 1.0
            for p in editable:
                prob *= probs[p] if p in s else 1.0 - probs[p]
            alleles.append(
                AlleleOutcome(
                    allele=_allele(s, editor), probability=prob, is_intended=s == intended
                )
            )
    outcome = EditOutcome(alleles=tuple(alleles), partial=False)
    p_exact = next((a.probability for a in alleles if a.is_intended), 0.0)
    burden = sum(probs.get(p, 0.0) for p in window.bystander_positions)
    return WindowOutcome(
        outcome=outcome,
        p_intended_exact=_prediction(p_exact),
        bystander_burden=_prediction(burden),
    )


def _prediction(value: float) -> Prediction[float]:
    """Wrap a baseline scalar in a calibrated 80% heuristic prediction."""
    return Prediction[float](
        value=value,
        interval=(max(0.0, value - _INTERVAL_HALF), value + _INTERVAL_HALF),
        interval_level=0.80,
        method=UncertaintyMethod.HEURISTIC,
        in_distribution=True,
        calibrated=False,
    )


def recommend_window(
    scored: Sequence[tuple[BaseEditWindow, WindowOutcome]],
) -> tuple[BaseEditWindow, WindowOutcome] | None:
    """Return the editor/guide maximizing clean-edit probability.

    The recommendation prefers the highest ``p_intended_exact`` and, on a tie,
    the lower ``bystander_burden`` — surfacing the cleanliness/bystander tradeoff.
    """
    if not scored:
        return None
    return max(
        scored,
        key=lambda sw: (sw[1].p_intended_exact.value, -sw[1].bystander_burden.value),
    )


class _ModelZooAdapter(WeightGate):
    """Shared base for the trained base-edit outcome adapters (lazy, gated).

    Trained weights resolve through the **consent-gated, checksum-verified** model
    zoo (:class:`~alleleforge.model_zoo.loader.WeightGate`); the forward pass over
    those weights lands with the real-weights integration. Use
    :class:`BaseEditOutcomePredictor` meanwhile.
    """

    name = ""

    def model_card(self) -> ModelCard:
        """Return the adapter's model card (raises if not registered)."""
        return self._registry.get(self.card_name)

    def predict(self, window: BaseEditWindow, editor: BaseEditor) -> WindowOutcome:
        """Resolve the license gate, then refuse — this is an out-of-scope placeholder.

        ``BeHiveAdapter`` is a license-gated placeholder, not a supported model: its
        upstream (BE-Hive) is TensorFlow-1-era and redundant with the wired **BE-DICT**
        model. See ``specs/cross-check-models-scope.md``.

        Raises:
            ConsentError / LicenseError / ChecksumError: From the weight gate.
            NotImplementedError: Always — use :class:`BeDictAdapter` (real) or
                :class:`BaseEditOutcomePredictor` (baseline) for this axis.
        """
        self.resolve_weights()
        raise NotImplementedError(  # pragma: no cover - out of supported scope (see scope spec)
            f"{self.name} is an out-of-scope placeholder (TF1-era/redundant upstream; "
            "see specs/cross-check-models-scope.md). Use BeDictAdapter for the real "
            "base-edit outcome model."
        )


#: AlleleForge editor name -> BE-DICT trained-model name. BE-DICT covers ABEmax,
#: ABE8e, BE4max (== CBE4max), Target-AID; editors outside this set are unsupported.
_BEDICT_EDITORS = {"ABE8e": "ABE8e", "CBE4max": "BE4max"}


@contextlib.contextmanager
def _chdir(path: Path) -> Iterator[None]:
    """Temporarily change the working directory (BE-DICT loads weights cwd-relative)."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _require_bedict(repo: Path) -> tuple[Any, Any]:  # pragma: no cover - needs extra + checkout
    """Import torch + BE-DICT's model class from a checkout, or raise a helpful error."""
    try:
        import torch

        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from criscas.predict_model import BEDICT_CriscasModel
    except ImportError as exc:
        raise RuntimeError(
            "the trained BE-DICT model requires PyTorch and a BE-DICT checkout. "
            "Clone https://github.com/uzh-dqbm-cmi/crispr and point the adapter at it "
            "(repo_dir=... or $ALLELEFORGE_BEDICT_REPO); see "
            "specs/base-outcome-integration.md"
        ) from exc
    return torch, BEDICT_CriscasModel


class BeDictAdapter(_ModelZooAdapter):
    """The real trained BE-DICT base-edit outcome model (consent-gated, opt-in).

    Runs BE-DICT's per-base attention model (Marquart et al., *Nat Commun* 2021,
    MIT) for the requested editor and turns its per-position edit probabilities into
    the same window-allele distribution the baseline produces — so the trained point
    estimates flow through the identical allele math. The interval stays heuristic
    (``calibrated=False``) until conformal calibration lands.

    BE-DICT ships as a Git repo (not a PyPI package) and loads its weights relative
    to the working directory, so the adapter points at a checkout via ``repo_dir`` /
    ``$ALLELEFORGE_BEDICT_REPO`` and runs it in-process under a cwd guard. Opt-in,
    gated behind the ``real_weights`` marker; CI stays weight-free.
    """

    name = "BE-DICT"
    card_name = "be-dict"

    def __init__(
        self,
        *,
        repo_dir: str | Path | None = None,
        device: str = "cpu",
        registry: ModelRegistry | None = None,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        cache_dir: str | Path | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        """Configure the BE-DICT checkout, device, and model-zoo gate.

        Args:
            repo_dir: Path to a BE-DICT (``uzh-dqbm-cmi/crispr``) checkout. Defaults
                to ``$ALLELEFORGE_BEDICT_REPO``.
            device: Torch device for inference (``"cpu"``/``"cuda"``).
            registry: Model-card registry (defaults to the bundled cards).
            use: The use the weights are loaded for (drives the license gate).
            consent: Must be ``True`` to authorize use of the weights.
            cache_dir: Override for the checkpoint cache (unused on this path).
            downloader: Injected fetcher (unused on this path).
        """
        super().__init__(
            registry=registry,
            use=use,
            consent=consent,
            cache_dir=cache_dir,
            downloader=downloader,
        )
        self._repo = Path(repo_dir or os.environ.get("ALLELEFORGE_BEDICT_REPO", ""))
        self._device = device

    def supported_editor(self, editor: BaseEditor) -> bool:
        """Return whether BE-DICT has a trained model for ``editor``."""
        return editor.name in _BEDICT_EDITORS

    def predict(self, window: BaseEditWindow, editor: BaseEditor) -> WindowOutcome:
        """Predict the window outcome with the trained BE-DICT model.

        Raises:
            ValueError: If BE-DICT has no model for ``editor``.
            ConsentError / LicenseError: From the model-zoo gate.
        """
        if not self.supported_editor(editor):
            raise ValueError(
                f"BE-DICT has no trained model for editor {editor.name!r}; "
                f"supported: {sorted(_BEDICT_EDITORS)}"
            )
        self.resolve_weights()  # consent + license gate; records provenance
        return self._predict_with_model(window, editor)  # pragma: no cover - needs extra

    def edit_probabilities(  # pragma: no cover - needs the extra + a BE-DICT checkout
        self, spacer: str, editor: BaseEditor
    ) -> dict[int, float]:
        """Return BE-DICT's mean per-position edit probability, keyed 0-based.

        The parity surface: keys are BE-DICT ``base_pos`` (0-based positions of the
        target base in the 20-nt protospacer), values are the mean edited-class
        probability across BE-DICT's five trained folds.
        """
        torch, model_cls = _require_bedict(self._repo)
        import pandas as pd

        frame = pd.DataFrame({"ID": ["alleleforge"], "seq": [spacer.upper()]})
        with _chdir(self._repo / "criscas"):
            model = model_cls(_BEDICT_EDITORS[editor.name], torch.device(self._device))
            pred_runs, _ = model.predict_from_dataframe(frame)
        # Aggregate the ensemble manually (upstream select_prediction breaks on modern
        # pandas). Mean of the edited-class probability per target-base position.
        means = pred_runs.groupby("base_pos")["prob_score_class1"].mean()
        return {int(pos): float(prob) for pos, prob in means.items()}

    def _predict_with_model(  # pragma: no cover - needs the extra + a BE-DICT checkout
        self, window: BaseEditWindow, editor: BaseEditor
    ) -> WindowOutcome:
        """Run BE-DICT and assemble the window outcome from its probabilities."""
        by_basepos = self.edit_probabilities(str(window.spacer.sequence), editor)
        editable = sorted({*window.target_positions, *window.bystander_positions})
        # AlleleForge positions are 1-based from the PAM-distal end; BE-DICT base_pos
        # is 0-based from the same (5') end -> p maps to base_pos p-1.
        probs = {p: by_basepos.get(p - 1, 0.0) for p in editable}
        return _assemble_window_outcome(window, editor, probs)


class BeHiveAdapter(_ModelZooAdapter):
    """BE-Hive placeholder — out of supported scope (see cross-check-models-scope)."""

    name = "BE-Hive"
    card_name = "be-hive"
