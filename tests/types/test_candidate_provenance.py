"""Tests for design candidate, ranked menu, and provenance models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alleleforge.types.candidate import DesignCandidate, RankedMenu
from alleleforge.types.edit import AlleleOutcome, Chemistry, EditOutcome
from alleleforge.types.guide import PAM, Guide, Spacer
from alleleforge.types.offtarget import OffTargetReport
from alleleforge.types.prediction import Prediction, UncertaintyMethod
from alleleforge.types.provenance import (
    DatasetVersion,
    ModelCheckpoint,
    Provenance,
    ToolVersion,
)
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand


def _guide() -> Guide:
    return Guide(
        spacer=Spacer(sequence=DNASequence("A" * 20)),
        pam=PAM(pattern="NGG"),
        pam_sequence=DNASequence("TGG"),
        placement=GenomicInterval(chrom="c", start=0, end=20, strand=Strand.PLUS),
        cut_site=17,
    )


def _candidate(value: float) -> DesignCandidate:
    return DesignCandidate(
        chemistry=Chemistry.CAS9_NUCLEASE,
        guide=_guide(),
        efficiency=Prediction[float](
            value=value, interval=(value - 0.1, value + 0.1), method=UncertaintyMethod.ENSEMBLE
        ),
        outcome=EditOutcome(alleles=(AlleleOutcome(allele="A", probability=1.0),)),
        offtarget=OffTargetReport(spacer="A" * 20, pam="NGG"),
    )


def test_candidate_has_reagent() -> None:
    assert _candidate(0.6).has_reagent
    assert not DesignCandidate(chemistry=Chemistry.PRIME).has_reagent


def test_ranked_menu_best_and_empty() -> None:
    menu = RankedMenu(candidates=(_candidate(0.8), _candidate(0.5)))
    assert menu.best is not None
    assert menu.best.efficiency is not None
    assert menu.best.efficiency.value == pytest.approx(0.8)
    assert RankedMenu(candidates=()).best is None


def test_ranked_menu_pareto_and_rationale() -> None:
    menu = RankedMenu(
        candidates=(_candidate(0.8), _candidate(0.5)),
        rationale="weighted sum: efficiency dominates",
        pareto_front=(0,),
    )
    assert menu.pareto_front == (0,)
    assert "weighted" in (menu.rationale or "")


def test_provenance_requires_tz_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Provenance(
            alleleforge_version="0.1.0",
            seed=1,
            timestamp=datetime(2026, 6, 3),  # naive  # noqa: DTZ001
        )


def test_provenance_normalizes_to_utc() -> None:
    p = Provenance.capture(
        alleleforge_version="0.1.0.dev0",
        seed=20240501,
        timestamp=datetime(2026, 6, 3, 12, tzinfo=UTC),
        tools=(ToolVersion(name="PRIDICT2.0", version="2.0"),),
        datasets=(DatasetVersion(name="gnomad", version="v4.1"),),
        models=(ModelCheckpoint(name="ABE8e-card", version="1"),),
    )
    assert p.timestamp.tzinfo is UTC
    assert p.tools[0].name == "PRIDICT2.0"
    assert p.seed == 20240501


def test_provenance_capture_defaults_timestamp() -> None:
    p = Provenance.capture(alleleforge_version="0.1.0", seed=1)
    assert p.timestamp.tzinfo is not None


def test_full_menu_with_provenance_roundtrips_json() -> None:
    menu = RankedMenu(
        candidates=(_candidate(0.7),),
        provenance=Provenance.capture(
            alleleforge_version="0.1.0.dev0",
            seed=20240501,
            timestamp=datetime(2026, 6, 3, tzinfo=UTC),
        ),
    )
    payload = menu.model_dump_json()
    restored = RankedMenu.model_validate_json(payload)
    assert restored.best is not None
    assert restored.provenance is not None
    assert restored.provenance.seed == 20240501
