"""Which vector a pegRNA is cloned into, and the length at which a donor stops being an oligo.

`oligos_for` silently substitutes the default pegRNA acceptor when the scheme it was handed
cannot receive a 3' extension -- documented behaviour, because an sgRNA vector physically
cannot take one. The gate deciding that is `ext_top_overhang is not None and
ext_bottom_overhang is not None`, and nothing measured either side of it: inverted, a real
pegRNA scheme is rejected and the user's requested vector is swapped for the default without
a word, and the oligos they order have the wrong sticky ends for the backbone on their bench.

`_ext_overhangs` carries the same condition in De Morgan's mirror form, and a scheme with only
*one* overhang defined has to be refused there by name rather than splicing a `None` into an
oligo sequence.
"""

from __future__ import annotations

import pytest

from alleleforge.report.oligos import (
    LENTIGUIDE_BSMBI,
    MAX_SSODN_NT,
    PEGRNA_GG_BSAI,
    VectorScheme,
    donor_oligo,
    oligos_for,
    pegrna_oligos,
)
from alleleforge.types.candidate import RankedMenu
from alleleforge.types.guide import HDRDonor
from alleleforge.types.sequence import DNASequence

#: A pegRNA-capable scheme that is *not* the default, so a substitution is visible.
_OTHER_PEGRNA_SCHEME = VectorScheme(
    name="test-pegrna-acceptor",
    enzyme="BsmBI",
    top_overhang="CACCG",
    bottom_overhang="AAAC",
    ext_top_overhang="GTGC",
    ext_bottom_overhang="CGCG",
    citation="test fixture",
)

#: Only one of the two extension overhangs: not a usable pegRNA scheme, and the shape a
#: hand-written or partially-migrated scheme definition actually takes.
_HALF_DEFINED = VectorScheme(
    name="test-half-defined",
    enzyme="BsaI",
    top_overhang="CACCG",
    bottom_overhang="AAAC",
    ext_top_overhang="GTGC",
    citation="test fixture",
)


def test_a_pegrna_scheme_is_kept_rather_than_replaced_by_the_default(
    prime_menu: RankedMenu,
) -> None:
    """The requested acceptor must survive to the oligos, or the sticky ends are wrong.

    Asserted against a scheme that is not `PEGRNA_GG_BSAI`, because with the default the
    substitution and the pass-through produce the same answer.
    """
    top = prime_menu.candidates[0]
    assert top.pegrna is not None
    oligos = oligos_for(top, scheme=_OTHER_PEGRNA_SCHEME)
    assert oligos is not None
    assert oligos.scheme.name == _OTHER_PEGRNA_SCHEME.name
    assert oligos.scheme.ext_top_overhang == "GTGC"


def test_an_sgrna_only_scheme_falls_back_for_a_pegrna_candidate(prime_menu: RankedMenu) -> None:
    """An sgRNA vector cannot receive a 3' extension, so the pegRNA acceptor is used."""
    top = prime_menu.candidates[0]
    assert LENTIGUIDE_BSMBI.ext_top_overhang is None
    oligos = oligos_for(top, scheme=LENTIGUIDE_BSMBI)
    assert oligos is not None
    assert oligos.scheme.name == PEGRNA_GG_BSAI.name


def test_a_half_defined_scheme_is_not_treated_as_pegrna_capable(prime_menu: RankedMenu) -> None:
    """One overhang is not a pair: the gate needs both, and the fallback applies."""
    top = prime_menu.candidates[0]
    oligos = oligos_for(top, scheme=_HALF_DEFINED)
    assert oligos is not None
    assert oligos.scheme.name == PEGRNA_GG_BSAI.name


def test_a_half_defined_scheme_is_refused_by_name_when_used_directly(
    prime_menu: RankedMenu,
) -> None:
    """Called past the gate, the missing overhang is an error, not a `None` in an oligo."""
    peg = prime_menu.candidates[0].pegrna
    assert peg is not None
    with pytest.raises(ValueError, match="test-half-defined"):
        pegrna_oligos(peg, scheme=_HALF_DEFINED)


def _donor(length: int) -> HDRDonor:
    """Return a concrete, re-cut-blocked donor of exactly ``length`` bases."""
    return HDRDonor(
        sequence=DNASequence("ACGT" * (length // 4) + "ACGT"[: length % 4]),
        recut_blocked=True,
    )


def test_a_donor_of_exactly_the_vendor_limit_is_not_flagged_as_over_it() -> None:
    """The warning is "beyond ~200 nt", so 200 is inside it and 201 is not.

    Relaxed by one, a donor a vendor will synthesize as a single oligo is reported as
    needing a dsDNA fragment or plasmid instead -- a real cost and delay, for a reagent
    that was orderable. Every existing fixture sits well clear of the boundary, so only
    the boundary separates the two.
    """
    at_limit = donor_oligo(_donor(MAX_SSODN_NT))
    assert len(at_limit.sequence) == MAX_SSODN_NT
    assert not any("beyond" in w for w in at_limit.warnings), at_limit.warnings

    over = donor_oligo(_donor(MAX_SSODN_NT + 1))
    assert any(f"{MAX_SSODN_NT + 1} nt, beyond" in w for w in over.warnings), over.warnings
