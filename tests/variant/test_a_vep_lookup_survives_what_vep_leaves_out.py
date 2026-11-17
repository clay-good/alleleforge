"""Four `or` fallbacks on the VEP path, none of which had a case.

The REST predictor and its parser are written defensively — `x or <default>` at every
point where a variant or a VEP record may be missing a field. Every fixture in the suite
supplies the field, so in each case the `or` was decided by the left side and the default
was never produced. They are not decoration:

* `Variant.build` is a `str` that may be empty. The assembly map matches neither GRCh38
  nor GRCh37 for it and falls through to `variant.build or "GRCh38"`; without that default
  the empty string is returned and the request URL becomes `.../vep//region/...`, which
  names no assembly at all. (The sibling `or ""` one line above is dead — `build` is typed
  `str` and cannot be `None` — and is left alone.)
* VEP returns a transcript block with no `consequence_terms` for some records, and the
  parser falls back to the record's `most_severe_consequence`. Without that fallback the
  severity `max()` is handed `None`.
* `is_canonical` reads `canonical` **or** `mane_select`, and every canonical fixture here
  sets both. VEP's MANE Select blocks do not always carry `canonical`, and that flag is
  what a reader uses to decide whether the consequence is the one that matters.
"""

from __future__ import annotations

import pytest

from alleleforge.types.variant import Variant
from alleleforge.variant.effect import Consequence, VepRestPredictor, parse_vep_response


def test_an_empty_build_is_a_build_a_variant_can_carry() -> None:
    """The premise for the check below."""
    assert Variant(chrom="chr11", pos=5226778, ref="A", alt="T", build="").build == ""


def test_an_empty_build_is_looked_up_against_the_default() -> None:
    variant = Variant(chrom="chr11", pos=5226778, ref="A", alt="T", build="")
    url = VepRestPredictor().request_url(variant)
    assert "grch38/region/chr11:5226779-5226779/T" in url
    assert "/vep//region/" not in url, "the URL names no assembly"


@pytest.mark.parametrize("build", ["hg38", "hg19", "custombuild"])
def test_a_build_that_is_given_is_the_one_used(build: str) -> None:
    """The other side, so the default above is not standing in for everything."""
    variant = Variant(chrom="chr11", pos=5226778, ref="A", alt="T", build=build)
    expected = {"hg38": "grch38", "hg19": "grch37"}.get(build, build)
    assert f"{expected}/region/" in VepRestPredictor().request_url(variant)


def test_a_transcript_with_no_terms_falls_back_to_the_records_most_severe() -> None:
    payload = [
        {
            "most_severe_consequence": "stop_gained",
            "transcript_consequences": [{"transcript_id": "ENST1", "canonical": 1}],
        }
    ]
    effect = parse_vep_response(payload)
    assert effect.consequence is Consequence.STOP_GAINED


def test_a_mane_select_transcript_is_canonical_without_the_canonical_flag() -> None:
    """VEP's MANE block does not always carry `canonical`, and this flag is read."""
    payload = [
        {
            "most_severe_consequence": "missense_variant",
            "transcript_consequences": [
                {
                    "transcript_id": "ENST1",
                    "consequence_terms": ["missense_variant"],
                    "mane_select": "NM_000518.5",
                }
            ],
        }
    ]
    assert parse_vep_response(payload).is_canonical is True


def test_a_transcript_that_is_neither_is_not_canonical() -> None:
    """The negative case: the flag has to be able to be false."""
    payload = [
        {
            "most_severe_consequence": "missense_variant",
            "transcript_consequences": [
                {"transcript_id": "ENST1", "consequence_terms": ["missense_variant"]}
            ],
        }
    ]
    assert parse_vep_response(payload).is_canonical is False
