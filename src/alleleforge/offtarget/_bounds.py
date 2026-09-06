"""Reject a non-finite number where a fraction is expected.

A range check spelled ``min=0.0, max=1.0`` — Click's, and the same shape in hand-written
guards — admits NaN, because every comparison against NaN is False. The three fractions
a user supplies to a search (``maf``, ``cfd_threshold``, ``mit_threshold``) each reached
a consumer that then compared against them, and a comparison against NaN is False there
too. What that meant depended only on which way the consumer's test was written:

* ``cfd < cfd_threshold and mit < mit_threshold`` is a *skip* condition, so a NaN
  threshold skipped nothing and reported every site — while the report's own
  description printed ``sites reported at CFD >= nan``, a cutoff it was not applying.
* ``max_af(populations) >= maf`` is an *include* condition, so a NaN ``maf`` admitted
  no record at all: every population off-target vanished and the report read as a clean
  bill of health on the population-safety axis, with no error and no warning.

The second is the recurring defect this project keeps finding — a real safety input
inert on the axis it governs — so the fix is to refuse the input, not to pick a
direction for it. ``inf`` is rejected by the same check: it is orderable, so it silently
means "report nothing" or "consider nothing" rather than being a threshold anyone meant.
"""

from __future__ import annotations

import math

__all__ = ["reject_non_finite"]


def reject_non_finite(**fractions: float) -> None:
    """Raise :class:`ValueError` naming any keyword whose value is not finite.

    Args:
        **fractions: Parameter name to supplied value.

    Raises:
        ValueError: If any value is NaN or infinite.
    """
    bad = sorted(name for name, value in fractions.items() if not math.isfinite(value))
    if bad:
        named = ", ".join(f"{name}={fractions[name]!r}" for name in bad)
        raise ValueError(
            f"a threshold must be a finite fraction in [0, 1]; got {named}. A non-finite "
            "value compares False against every score, which silently changes which "
            "sites are reported rather than filtering them at the cutoff you asked for."
        )
