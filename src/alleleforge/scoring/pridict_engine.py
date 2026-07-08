"""Wrap the external PRIDICT2.0 prime-editing design+score pipeline (opt-in).

PRIDICT2.0 (Mathis et al., *Nat Biotechnol* 2024; MIT-licensed) takes a target
sequence with a bracketed edit and **designs and scores its own pegRNAs** — it is
not a "score this pegRNA" function. So AlleleForge integrates it at the sequence
level: :class:`PridictEngineAdapter` hands PRIDICT2 an edit's genomic context and
surfaces its ranked designs, each carrying a calibrated efficiency
:class:`~alleleforge.types.prediction.Prediction` (point estimate from the real
trained ensemble; honest about its HEK/K562 training distribution).

PRIDICT2 is a multi-framework tool (a PyTorch attention-RNN ensemble plus a
TensorFlow DeepCas9 feature) distributed as a Git repository, not a Python
package. The adapter therefore shells out to the user's PRIDICT2 checkout: point
it at the repo and interpreter via the constructor or the
``ALLELEFORGE_PRIDICT2_REPO`` / ``ALLELEFORGE_PRIDICT2_PYTHON`` environment
variables. The forward pass is gated behind the ``real_weights`` test marker, so
CI never runs it; the pure CSV-parsing path is exercised in CI on a fixture.

See [`specs/pridict2-integration.md`] for the boundary decision and the staged
plan (P1 sequence-level wrap, here; P2 per-pegRNA parity, later).
"""

from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from alleleforge.model_zoo.loader import WeightGate
from alleleforge.model_zoo.registry import Downloader, ModelCard, ModelRegistry, ModelUse
from alleleforge.types.prediction import NOMINAL_INTERVAL_NOTE, Prediction, UncertaintyMethod

#: Cell lines PRIDICT2.0 predicts (and is trained on); the score column suffix.
PRIDICT2_CELL_LINES = ("HEK", "K562")

#: Heuristic interval half-width around the trained point estimate.
_INTERVAL_HALF = 0.15


@dataclass(frozen=True)
class PridictDesign:
    """One PRIDICT2.0 pegRNA design with its calibrated efficiency.

    Attributes:
        editing_position: PRIDICT2's reported edit position in the protospacer.
        pbs_length: Primer-binding-site length (nt).
        rt_length: Reverse-transcriptase-template length (nt).
        rt_overhang: RT-template 3' homology overhang length (nt).
        cell_line: The cell line the efficiency is predicted for (``HEK``/``K562``).
        efficiency: The predicted editing efficiency as a calibrated prediction
            (point = PRIDICT2 score / 100; interval heuristic).
    """

    editing_position: int
    pbs_length: int
    rt_length: int
    rt_overhang: int
    cell_line: str
    efficiency: Prediction[float]


class PridictEngineAdapter(WeightGate):
    """Sequence-level wrapper over the external PRIDICT2.0 design+score pipeline.

    Resolve the model through the consent-gated model zoo (PRIDICT2 is MIT, so it
    permits research *and* commercial use), then run PRIDICT2's ``single`` command
    on an edit sequence and return its top-ranked designs. Opt-in: needs a local
    PRIDICT2 checkout + its environment, and is gated behind ``real_weights``.
    """

    name = "pridict2-engine"
    card_name = "pridict2"

    def __init__(
        self,
        *,
        repo_dir: str | Path | None = None,
        python_executable: str | None = None,
        use_5folds: bool = False,
        registry: ModelRegistry | None = None,
        use: ModelUse = ModelUse.RESEARCH,
        consent: bool = False,
        cache_dir: str | Path | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        """Configure the PRIDICT2 checkout, interpreter, and model-zoo gate.

        Args:
            repo_dir: Path to the PRIDICT2 repository checkout. Defaults to
                ``$ALLELEFORGE_PRIDICT2_REPO``.
            python_executable: Interpreter with PRIDICT2's dependencies. Defaults
                to ``$ALLELEFORGE_PRIDICT2_PYTHON`` then ``"python"``.
            use_5folds: Average all five trained folds (slower, lower-variance)
                rather than the default single fold.
            registry: Model-card registry (defaults to the bundled cards).
            use: The use the model is loaded for (drives the license gate).
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
        self._repo = Path(repo_dir or os.environ.get("ALLELEFORGE_PRIDICT2_REPO", ""))
        self._python = python_executable or os.environ.get("ALLELEFORGE_PRIDICT2_PYTHON", "python")
        self._use_5folds = use_5folds

    def model_card(self) -> ModelCard:
        """Return the PRIDICT2.0 model card."""
        return self._registry.get(self.card_name)

    @staticmethod
    def _efficiency(score_percent: float) -> Prediction[float]:
        """Wrap a PRIDICT2 0-100 score as a calibrated [0, 1] efficiency prediction.

        The point estimate is the real trained model's score (rescaled); the
        interval is a documented heuristic spread until conformal calibration on a
        real validation set lands (R5). HEK/K562 are the training distribution, so
        the OOD flag is honest (in-distribution).
        """
        value = min(1.0, max(0.0, score_percent / 100.0))
        return Prediction[float](
            value=value,
            interval=(max(0.0, value - _INTERVAL_HALF), min(1.0, value + _INTERVAL_HALF)),
            interval_level=0.80,
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=True,
            calibrated=False,
            point_from_trained_model=True,  # real PRIDICT2 point; interval still heuristic
            notes=(NOMINAL_INTERVAL_NOTE,),
        )

    @classmethod
    def _parse_predictions(
        cls, csv_path: str | Path, *, cell_line: str, top_n: int
    ) -> list[PridictDesign]:
        """Parse a PRIDICT2 ``*_pegRNA_Pridict_full.csv`` into ranked designs.

        Pure (no subprocess), so it is unit-tested in CI on a fixture.

        Args:
            csv_path: Path to PRIDICT2's full-prediction CSV.
            cell_line: ``HEK`` or ``K562`` — selects the score column and ranking.
            top_n: Number of top designs to return.

        Returns:
            The ``top_n`` designs, highest predicted efficiency first.

        Raises:
            ValueError: If ``cell_line`` is not a PRIDICT2 cell line.
        """
        if cell_line not in PRIDICT2_CELL_LINES:
            raise ValueError(f"cell_line must be one of {PRIDICT2_CELL_LINES}; got {cell_line!r}")
        score_col = f"PRIDICT2_0_editing_Score_deep_{cell_line}"
        designs: list[PridictDesign] = []
        with open(csv_path, newline="") as handle:
            for row in csv.DictReader(handle):
                designs.append(
                    PridictDesign(
                        editing_position=int(float(row["Editing_Position"])),
                        pbs_length=int(float(row["PBSlength"])),
                        rt_length=int(float(row["RTlength"])),
                        rt_overhang=int(float(row["RToverhanglength"])),
                        cell_line=cell_line,
                        efficiency=cls._efficiency(float(row[score_col])),
                    )
                )
        designs.sort(key=lambda d: d.efficiency.value, reverse=True)
        return designs[:top_n]

    def design(
        self,
        edit_sequence: str,
        *,
        sequence_name: str = "alleleforge",
        cell_line: str = "HEK",
        top_n: int = 3,
    ) -> list[PridictDesign]:  # pragma: no cover - runs the external PRIDICT2 tool
        """Design and score pegRNAs for ``edit_sequence`` via PRIDICT2.0.

        Args:
            edit_sequence: Target sequence with a bracketed edit, e.g.
                ``"…(A/G)…"``, with >= 100 bp up/downstream (PRIDICT2's contract).
            sequence_name: Identifier passed to PRIDICT2 (names its output file).
            cell_line: ``HEK`` or ``K562`` — the efficiency context to rank by.
            top_n: Number of top designs to return.

        Returns:
            The top-ranked :class:`PridictDesign` objects.

        Raises:
            ConsentError / LicenseError: From the model-zoo gate.
            ValueError: If ``cell_line`` is invalid.
            FileNotFoundError: If the PRIDICT2 repo / output is not found.
        """
        if cell_line not in PRIDICT2_CELL_LINES:
            raise ValueError(f"cell_line must be one of {PRIDICT2_CELL_LINES}; got {cell_line!r}")
        self.resolve_weights()  # consent + license gate; records provenance
        script = self._repo / "pridict2_pegRNA_design.py"
        if not script.exists():
            raise FileNotFoundError(
                f"PRIDICT2 script not found at {script}; set repo_dir or "
                "$ALLELEFORGE_PRIDICT2_REPO to a PRIDICT2 checkout"
            )
        with tempfile.TemporaryDirectory() as out_dir:
            cmd = [
                self._python,
                "pridict2_pegRNA_design.py",
                "single",
                "--sequence-name",
                sequence_name,
                "--sequence",
                edit_sequence,
                "--output-dir",
                out_dir,
            ]
            if self._use_5folds:
                cmd.append("--use_5folds")
            subprocess.run(cmd, cwd=self._repo, check=True)
            csv_path = Path(out_dir) / f"{sequence_name}_pegRNA_Pridict_full.csv"
            return self._parse_predictions(csv_path, cell_line=cell_line, top_n=top_n)
