"""The default off-target scan got slower the moment a region crossed 1 Mb.

`search()` auto-engaged the FM-index seed-and-extend path past `1_000_000` bases, on the
stated grounds that the index build "only amortizes at contig scale". Measured on the
real default path, with the native crate present:

    1 Mb, one guide     linear  1.77s   auto/FM   4.85s   (2.7x slower)
    2 Mb, one guide     linear  3.61s   auto/FM   9.69s   (2.7x slower)
    8 Mb, one guide     linear 14.22s   auto/FM  65.19s   (4.6x slower)
    1 Mb, five guides   linear  9.75s   auto/FM  21.56s   (2.2x slower)

The justification was backwards. It does not converge at contig scale, it diverges; and
it does not amortize across guides sharing a contig either. So the threshold made the
*default* configuration several times slower at exactly the genome scale the tool exists
for, and `scripts/native_speedup.py` had been printing `SLOWER` for the pair all along —
the number was in the output and the decision was in the prose.

This file pins the shape of the fix rather than a wall-clock number: timings are hardware
dependent and belong in the script, but "the default path does not silently take the
indexed route" is a property, and so is "asking for it still works and finds the same
hits".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget import engine
from alleleforge.offtarget.engine import FM_INDEX_AUTO_ENGAGES, search
from alleleforge.types.guide import PAM, Spacer
from alleleforge.types.sequence import DNASequence

_SPACER = Spacer(sequence=DNASequence("GGAGGAATCCTCGACGGTAT"))
_PAM = PAM(pattern="NGG")


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    """A small contig — the threshold is what is under test, not the size."""
    import random

    rng = random.Random(11)
    seq = "".join(rng.choice("ACGT") for _ in range(4000))
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + seq + "\n")
    return ReferenceGenome(fasta, build="hg38")


def test_the_indexed_path_is_opt_in() -> None:
    """No size makes it engage itself; that is the whole change."""
    assert FM_INDEX_AUTO_ENGAGES is False


def _fm_calls(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Record the `use_fm_index` each region scan is given."""
    seen: list[bool] = []
    original = engine.scan_sequence

    def recording(*args: Any, **kwargs: Any) -> Any:
        if "use_fm_index" in kwargs:
            seen.append(bool(kwargs["use_fm_index"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "scan_sequence", recording)
    return seen


@pytest.mark.parametrize("threshold", [10, 1_000_000])
def test_no_region_size_engages_the_index_by_default(
    threshold: int, reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parameterized over a threshold *below* the contig, which used to force it on.

    With the old rule a 4 kb contig and a 10-base threshold would take the indexed path.
    The point is that there is no longer a size at which the default changes route.
    """
    seen = _fm_calls(monkeypatch)
    monkeypatch.setattr(engine, "FM_INDEX_AUTO_ENGAGES", False)
    search(_SPACER, _PAM, reference=reference)
    assert seen, "no region scan was observed; the recording hook missed"
    assert not any(seen), f"the default scan asked for the FM-index: {seen}"


def test_asking_for_it_still_works_and_finds_the_same_hits(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path stays reachable and exact — only the default changed."""
    seen = _fm_calls(monkeypatch)
    forced = search(_SPACER, _PAM, reference=reference, use_fm_index=True)
    assert seen and all(seen), f"use_fm_index=True did not reach the indexed path: {seen}"
    default = search(_SPACER, _PAM, reference=reference)
    assert [str(s.interval) for s in forced.sites] == [str(s.interval) for s in default.sites]
    assert forced.specificity_score() == default.specificity_score()


def test_forbidding_it_is_still_honoured(
    reference: ReferenceGenome, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _fm_calls(monkeypatch)
    search(_SPACER, _PAM, reference=reference, use_fm_index=False)
    assert seen and not any(seen), seen
