"""Chemistry, intent, and edit-outcome models.

These types describe *what* an edit is trying to do and *what distribution of
results* a chemistry is predicted to produce, independent of any particular
reagent geometry.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from alleleforge.types.variant import Variant

#: Tolerance for an outcome distribution's probabilities summing to 1.
_PROB_SUM_TOL = 1e-6


class Chemistry(StrEnum):
    """The editing chemistries AlleleForge designs for."""

    CAS9_NUCLEASE = "cas9_nuclease"
    BASE_ABE = "base_abe"
    BASE_CBE = "base_cbe"
    PRIME = "prime"


class EditIntent(StrEnum):
    """What the user wants the edit to accomplish.

    The intent decides which allele the target genome is assumed to *carry* and
    which one the reagent must *write*, so it changes the sequence guides are
    enumerated against, not merely how a result is labeled.

    Attributes:
        CORRECT: The genome carries the alternate (disease) allele; write the
            reference back.
        KNOCK_OUT: Disrupt the locus. No allele is written — the double-strand
            break's NHEJ indels are the product — so no allele is carried either.
        INSTALL: The genome carries the reference; write the alternate allele
            (engineering a variant in, e.g. to build a disease model).
        REVERT: Undo a previously installed edit — the genome carries the
            alternate allele and the reference is written back. **Mechanically
            identical to CORRECT** and handled by the same branches throughout;
            it exists so a run's provenance records *why* the edit was made,
            which CORRECT (repairing a pathogenic allele) and REVERT (returning
            an engineered line to wild type) do not share. A test pins the
            equivalence, because it is currently spelled out in several
            independent ``intent in (CORRECT, REVERT)`` checks rather than
            centralized.
    """

    CORRECT = "correct"
    KNOCK_OUT = "knock_out"
    INSTALL = "install"
    REVERT = "revert"


class AlleleOutcome(BaseModel):
    """One possible resulting allele and its predicted probability."""

    model_config = ConfigDict(frozen=True)

    allele: str
    probability: float
    is_intended: bool = False

    @model_validator(mode="after")
    def _check_probability(self) -> AlleleOutcome:
        """Validate the probability lies in ``[0, 1]``."""
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"probability {self.probability} not in [0, 1]")
        return self


class EditOutcome(BaseModel):
    """A distribution over resulting alleles for one edit.

    Attributes:
        alleles: The (allele, probability) outcomes. Probabilities must sum to
            ~1 unless the distribution is explicitly marked ``partial``.
        partial: ``True`` when the listed alleles cover only part of the
            outcome space (the remainder is unenumerated byproducts).
    """

    model_config = ConfigDict(frozen=True)

    alleles: tuple[AlleleOutcome, ...]
    partial: bool = False

    @model_validator(mode="after")
    def _check_distribution(self) -> EditOutcome:
        """Validate probabilities and (for complete distributions) their sum."""
        if not self.alleles:
            raise ValueError("outcome distribution is empty")
        total = sum(a.probability for a in self.alleles)
        if not self.partial and not math.isclose(total, 1.0, abs_tol=1e-3):
            raise ValueError(f"probabilities sum to {total}, expected ~1.0")
        if total > 1.0 + _PROB_SUM_TOL:
            raise ValueError(f"probabilities sum to {total} > 1")
        return self

    @property
    def most_likely(self) -> AlleleOutcome:
        """Return the highest-probability allele outcome."""
        return max(self.alleles, key=lambda a: a.probability)

    @property
    def p_intended(self) -> float:
        """Return the summed probability of all intended-allele outcomes."""
        return sum(a.probability for a in self.alleles if a.is_intended)


class EditStrategy(BaseModel):
    """Binds a target variant to a chemistry and an intent.

    Attributes:
        variant: The normalized target variant.
        chemistry: The chemistry chosen to address it.
        intent: What the edit is meant to accomplish.
    """

    model_config = ConfigDict(frozen=True)

    variant: Variant
    chemistry: Chemistry
    intent: EditIntent
