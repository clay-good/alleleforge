"""Off-target engine — reference, population, and haplotype aware (Phase 5).

AlleleForge's safety core and a primary point of novelty: population- and
haplotype-aware off-target nomination for every chemistry, behind one
:func:`~alleleforge.offtarget.engine.search` call returning an ancestry-stratified
:class:`~alleleforge.types.offtarget.OffTargetReport`.

Off-target nominations are **computational** and must be experimentally
validated; AlleleForge narrows the search, it does not replace GUIDE-seq /
CHANGE-seq confirmation.
"""

from __future__ import annotations

from alleleforge.offtarget.cache import OffTargetCache, search_signature
from alleleforge.offtarget.cas_offinder_adapter import CasOffinderAdapter
from alleleforge.offtarget.engine import (
    DEFAULT_CFD_THRESHOLD,
    DEFAULT_MIT_THRESHOLD,
    low_stringency_pam,
    search,
)
from alleleforge.offtarget.haplotype import enumerate_haplotype_sites
from alleleforge.offtarget.population import (
    enumerate_patient_sites,
    enumerate_population_sites,
)
from alleleforge.offtarget.scoring import (
    CFD_PAM_WEIGHTS,
    MIT_WEIGHTS,
    Cas12aCfdScorer,
    CfdScorer,
    MitScorer,
    OffTargetScorer,
    cas12a_cfd_score,
    cfd_score,
    mit_score,
)

__all__ = [
    "CFD_PAM_WEIGHTS",
    "DEFAULT_CFD_THRESHOLD",
    "DEFAULT_MIT_THRESHOLD",
    "MIT_WEIGHTS",
    "Cas12aCfdScorer",
    "CasOffinderAdapter",
    "CfdScorer",
    "MitScorer",
    "OffTargetCache",
    "OffTargetScorer",
    "cas12a_cfd_score",
    "cfd_score",
    "enumerate_haplotype_sites",
    "enumerate_patient_sites",
    "enumerate_population_sites",
    "low_stringency_pam",
    "mit_score",
    "search",
    "search_signature",
]
