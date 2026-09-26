"""``populations``, ``max_freq`` and the ``min_freq`` gate, on their own boundaries.

Each of these three answers a population-frequency question the safety surfaces act
on -- which cohorts carry a haplotype, how common it is among the ones asked about,
and whether it clears the threshold. The panel tests pinned them only through
fixtures where every population differed and none sat on a boundary, so a zero-
frequency population still counted as a carrier, ``max_freq`` never had to prefer
the larger of two requested frequencies, and no haplotype was ever exactly at
``min_freq``. Frequencies in a real panel do all three.
"""

from __future__ import annotations

from alleleforge.data.haplotypes import Haplotype, HaplotypePanel
from alleleforge.types.sequence import GenomicInterval, Strand
from alleleforge.types.variant import Variant

_WINDOW = GenomicInterval(chrom="chr2", start=100, end=160, strand=Strand.PLUS)


def _hap(hap_id: str, frequencies: dict[str, float]) -> Haplotype:
    return Haplotype(
        hap_id=hap_id,
        interval=_WINDOW,
        variants=(Variant(chrom="chr2", pos=120, ref="A", alt="G"),),
        frequencies=frequencies,
        source="test",
    )


def test_a_population_listed_at_zero_frequency_is_not_a_carrier() -> None:
    """A panel row can list a cohort it was measured in and found nothing in.

    Reporting it as carrying the haplotype names a population in an off-target
    disclosure that does not carry the allele the disclosure is about.
    """
    hap = _hap("H1", {"AFR": 0.0, "EUR": 0.20})
    assert hap.populations == ("EUR",)


def test_max_freq_over_requested_populations_takes_the_largest() -> None:
    """Two requested cohorts, different frequencies: the answer is the riskier one."""
    hap = _hap("H1", {"AFR": 0.30, "EUR": 0.02, "EAS": 0.50})
    assert hap.max_freq(["AFR", "EUR"]) == 0.30, "the smaller would understate the risk"
    assert hap.max_freq(["EUR"]) == 0.02, "a cohort not asked about must not raise it"
    assert hap.max_freq() == 0.50, "no request means every population the panel has"


def test_an_unlisted_population_contributes_nothing_rather_than_failing() -> None:
    """Asking about a cohort the panel never measured is zero, not an error."""
    hap = _hap("H1", {"AFR": 0.30})
    assert hap.max_freq(["EUR"]) == 0.0


def test_a_haplotype_exactly_at_min_freq_is_reported() -> None:
    """The gate is 'at or above': a haplotype on the threshold clears it.

    ``min_freq`` is a safety floor, so the boundary case has to fall on the side that
    discloses. Excluding it drops exactly the haplotype a threshold was set to catch.
    """
    haps = [_hap("ON", {"AFR": 0.01}), _hap("UNDER", {"AFR": 0.009})]
    panel = HaplotypePanel(haps, source="test")
    found = panel.common_haplotypes(_WINDOW, min_freq=0.01)
    assert [h.hap_id for h in found] == ["ON"]
