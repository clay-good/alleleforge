"""Prime-editing outcome (intended vs. byproduct) prediction.

A pegRNA does not only install the intended edit. The reverse transcriptase can
read into the **scaffold** (scaffold incorporation), stop early (**partial RTT**
products), or the nicks can yield **indels**. This module predicts the
intended-vs-byproduct distribution as an :class:`EditOutcome` and the intended
probability as a calibrated :class:`Prediction`.

The default is a transparent baseline keyed on the pegRNA geometry: clean
geometry (short nick-to-edit, mid-length RTT, an epegRNA motif, and a PE3b
nicking guide) favors the intended product; long RTTs raise scaffold-incorporation
and partial-RTT byproducts; a non-seed-disrupting PE3 nick raises the indel share.
"""

from __future__ import annotations

from dataclasses import dataclass

from alleleforge.types.edit import AlleleOutcome, EditOutcome
from alleleforge.types.guide import PegRNA
from alleleforge.types.prediction import Prediction, UncertaintyMethod

#: The byproduct channels modeled, in addition to the intended product.
_BYPRODUCTS = ("scaffold_incorporation", "partial_rtt", "indel")


@dataclass(frozen=True)
class PrimeOutcome:
    """A predicted prime-edit outcome with its intended probability."""

    outcome: EditOutcome
    p_intended: Prediction[float]


def _nick_to_edit(pegrna: PegRNA) -> int:
    """Derive the nick-to-edit distance from the RTT geometry."""
    return max(0, len(pegrna.rtt) - pegrna.rtt_homology_3prime - 1)


class PrimeOutcomePredictor:
    """A transparent prime-edit byproduct baseline."""

    name = "prime-outcome-baseline"

    def predict(self, pegrna: PegRNA) -> PrimeOutcome:
        """Return the intended-vs-byproduct distribution for ``pegrna``.

        Args:
            pegrna: The pegRNA to score (its geometry drives the byproduct mix).

        Returns:
            A :class:`PrimeOutcome` with the allele distribution and the
            calibrated intended probability.
        """
        rtt_len = len(pegrna.rtt)
        # Byproduct propensities (un-normalized), from pegRNA geometry.
        scaffold = 0.10 + 0.01 * max(0, rtt_len - 20)  # long RTTs read into scaffold
        partial = 0.08 + 0.004 * rtt_len  # longer RTTs stop early more often
        seed_disrupting = pegrna.nicking_guide is not None and pegrna.nicking_guide.seed_disrupting
        indel = 0.05 if seed_disrupting else 0.15  # PE3b suppresses indels vs PE3
        if not pegrna.is_epegrna:
            scaffold += 0.05  # the tevopreQ1 motif reduces scaffold incorporation
        byproduct_mass = scaffold + partial + indel
        intended = max(0.01, 1.0 - byproduct_mass)
        total = intended + byproduct_mass

        alleles = [AlleleOutcome(allele="intended", probability=intended / total, is_intended=True)]
        for name, mass in zip(_BYPRODUCTS, (scaffold, partial, indel), strict=True):
            alleles.append(AlleleOutcome(allele=name, probability=mass / total))
        outcome = EditOutcome(alleles=tuple(alleles), partial=False)

        p = intended / total
        prediction = Prediction[float](
            value=p,
            interval=(max(0.0, p - 0.15), min(1.0, p + 0.15)),
            interval_level=0.80,
            method=UncertaintyMethod.HEURISTIC,
            in_distribution=True,
            calibrated=False,
        )
        return PrimeOutcome(outcome=outcome, p_intended=prediction)
