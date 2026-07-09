"""Tests for the consequence model, the static predictor, and the VEP backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alleleforge.types.variant import Variant
from alleleforge.variant.effect import (
    Consequence,
    Impact,
    StaticEffectPredictor,
    VariantEffect,
    VepRestPredictor,
    impact_of,
    parse_vep_response,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def _vep_payload() -> list[dict[str, Any]]:
    return json.loads((_FIXTURES / "vep_hbb_missense.json").read_text())


def test_impact_ordering_is_severity() -> None:
    assert Impact.HIGH > Impact.MODERATE > Impact.LOW > Impact.MODIFIER


def test_impact_of_known_consequences() -> None:
    assert impact_of(Consequence.STOP_GAINED) is Impact.HIGH
    assert impact_of(Consequence.MISSENSE) is Impact.MODERATE
    assert impact_of(Consequence.SYNONYMOUS) is Impact.LOW
    assert impact_of(Consequence.INTRON) is Impact.MODIFIER


def test_static_predictor_returns_registered_effect() -> None:
    var = Variant(chrom="chr2", pos=60099, ref="A", alt="T")
    effect = VariantEffect(consequence=Consequence.MISSENSE, impact=Impact.MODERATE, gene="HBB")
    predictor = StaticEffectPredictor()
    predictor.add(var, effect)
    assert predictor.predict(var).gene == "HBB"


def test_static_predictor_defaults_to_other() -> None:
    var = Variant(chrom="chr2", pos=1, ref="A", alt="G")
    effect = StaticEffectPredictor().predict(var, transcript="ENST1")
    assert effect.consequence is Consequence.OTHER
    assert effect.impact is Impact.MODIFIER
    assert effect.transcript == "ENST1"


def test_static_predictor_seeded_table() -> None:
    var = Variant(chrom="chr2", pos=10, ref="G", alt="A")
    table = {str(var): VariantEffect(consequence=Consequence.SPLICE_DONOR, impact=Impact.HIGH)}
    assert StaticEffectPredictor(table).predict(var).impact is Impact.HIGH


# --- VEP REST backend (recorded fixture, injected fetcher, no network) -----------


def test_parse_vep_response_picks_mane_canonical() -> None:
    effect = parse_vep_response(_vep_payload())
    assert effect.consequence is Consequence.MISSENSE
    assert effect.impact is Impact.MODERATE
    assert effect.gene == "HBB"
    assert effect.transcript == "ENST00000335295"
    assert effect.hgvs_p == "ENSP00000333994.3:p.Glu7Val"
    assert effect.is_canonical is True


def test_select_transcript_prefers_mane_over_earlier_canonical() -> None:
    # A canonical-but-not-MANE transcript precedes the MANE Select one. VEP does
    # not guarantee MANE-first ordering, so the default MANE_SELECT request must
    # still return the MANE transcript, not the first merely-canonical block.
    payload = [
        {
            "most_severe_consequence": "missense_variant",
            "transcript_consequences": [
                {
                    "transcript_id": "ENST_CANON",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                    "canonical": 1,
                },
                {
                    "transcript_id": "ENST_MANE",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                    "mane_select": "NM_999.1",
                },
            ],
        }
    ]
    assert parse_vep_response(payload).transcript == "ENST_MANE"


def test_select_transcript_ignores_falsy_mane_select() -> None:
    # A transcript carrying an explicit falsy mane_select is not MANE Select; the
    # canonical transcript is chosen and is_canonical reflects only real flags.
    payload = [
        {
            "most_severe_consequence": "missense_variant",
            "transcript_consequences": [
                {
                    "transcript_id": "ENST_FALSY",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                    "mane_select": "",
                },
                {
                    "transcript_id": "ENST_CANON",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                    "canonical": 1,
                },
            ],
        }
    ]
    effect = parse_vep_response(payload)
    assert effect.transcript == "ENST_CANON"
    assert effect.is_canonical is True


def test_parse_vep_response_picks_most_severe_within_impact_tier() -> None:
    # A transcript listing several SO terms in the same impact tier must report the
    # SO-most-severe one, not whichever VEP happened to list first. splice_donor
    # outranks frameshift (both HIGH); the wrong pick would mis-route chemistry.
    payload = [
        {
            "transcript_consequences": [
                {
                    "transcript_id": "ENST_X",
                    "consequence_terms": ["frameshift_variant", "splice_donor_variant"],
                    "mane_select": "NM_1.1",
                }
            ]
        }
    ]
    assert parse_vep_response(payload).consequence is Consequence.SPLICE_DONOR
    # ...and within the LOW tier, splice_region outranks synonymous.
    payload[0]["transcript_consequences"][0]["consequence_terms"] = [
        "synonymous_variant",
        "splice_region_variant",
    ]
    assert parse_vep_response(payload).consequence is Consequence.SPLICE_REGION


def test_parse_vep_response_specific_transcript() -> None:
    effect = parse_vep_response(_vep_payload(), transcript="ENST00000633227")
    assert effect.consequence is Consequence.UPSTREAM
    assert effect.impact is Impact.MODIFIER


def test_parse_vep_response_empty_is_intergenic() -> None:
    assert parse_vep_response([]).consequence is Consequence.INTERGENIC


def test_parse_vep_response_no_transcripts_uses_most_severe() -> None:
    payload = [{"most_severe_consequence": "stop_gained"}]
    effect = parse_vep_response(payload)
    assert effect.consequence is Consequence.STOP_GAINED
    assert effect.impact is Impact.HIGH


def test_parse_vep_response_unknown_term_degrades_to_other() -> None:
    payload = [{"transcript_consequences": [{"consequence_terms": ["brand_new_so_term"]}]}]
    assert parse_vep_response(payload).consequence is Consequence.OTHER


def test_vep_request_url_maps_assembly() -> None:
    hg19 = Variant(chrom="chr11", pos=5226778, ref="A", alt="T", build="hg19")
    assert "grch37/region/chr11:5226779-5226779/T" in VepRestPredictor().request_url(hg19)
    novel = Variant(chrom="chr1", pos=10, ref="C", alt="G", build="custombuild")
    # An unrecognized build name passes through verbatim (lowercased in the URL).
    assert "custombuild/region/chr1:11-11/G" in VepRestPredictor().request_url(novel)


def test_parse_vep_response_specific_transcript_absent_falls_back() -> None:
    # Asking for a transcript not present falls through to the canonical one.
    effect = parse_vep_response(_vep_payload(), transcript="ENST_NOT_PRESENT")
    assert effect.transcript == "ENST00000335295"


def test_vep_predictor_uses_injected_fetcher_and_caches() -> None:
    var = Variant(chrom="chr2", pos=60099, ref="A", alt="T", build="hg38")
    calls: list[str] = []

    def fetcher(url: str) -> list[dict[str, Any]]:
        calls.append(url)
        return _vep_payload()

    predictor = VepRestPredictor(fetcher=fetcher)
    first = predictor.predict(var)
    second = predictor.predict(var)  # served from cache, no second fetch
    assert first.gene == "HBB" and first == second
    assert len(calls) == 1
    assert "GRCh38".lower() in calls[0] and "chr2:60100-60100" in calls[0]
