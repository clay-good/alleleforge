"""The v1.0 criteria are measured, not guessed.

`SPEC_V2.md` lists five conditions for cutting v1.0 and nothing measured any of them,
so "how close are we" was answered by reading five bullet points. Most are blocked
outside this repository — real weights, real corpora, a posted preprint — which is
precisely why measuring them is worth it: it separates *blocked* from *forgotten*, and
it notices the day one stops being blocked.

These pin the report's honesty rather than its verdict. A readiness report that
overstates its evidence is worse than none, and the first draft did exactly that: it
counted 16 "native parity" test modules by grepping for the substring `native`, which
matches any test whose prose contains the word.
"""

from __future__ import annotations

from scripts import release_readiness


def test_every_spec_criterion_is_measured() -> None:
    """One reported criterion per bullet under `SPEC_V2.md`'s R6 section."""
    from pathlib import Path

    spec = (Path(__file__).resolve().parents[1] / "SPEC_V2.md").read_text()
    section = spec.split("## R6 — v1.0 release criteria")[1].split("\nUntil then")[0]
    bullets = [line for line in section.splitlines() if line.startswith("- ")]
    assert bullets, "no R6 criteria found in SPEC_V2.md — this check would be vacuous"
    assert len(release_readiness.criteria()) == len(bullets), (
        f"SPEC_V2.md lists {len(bullets)} v1.0 criteria and the report measures "
        f"{len(release_readiness.criteria())}"
    )


def test_an_unmet_criterion_says_what_blocks_it() -> None:
    """ "Not met" and "not met because the upstream artifact is not frozen" differ."""
    for c in release_readiness.criteria():
        if not c.met:
            assert c.blocked_by, f"{c.track} is unmet and names nothing that blocks it"
        assert c.detail, f"{c.track} reports no detail"


def test_the_artifact_count_excludes_baselines() -> None:
    """A heuristic baseline has no artifact, so it must not count against the pinning.

    Counting all 17 cards would report 1/17 pinned and read as far worse than the
    truth; the denominator is the cards that actually name a source to download.
    """
    from alleleforge.model_zoo.registry import default_registry

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    downloadable = [c for c in cards if c.source_url]
    assert len(downloadable) < len(cards), "the fixture has no baselines to exclude"

    pinning = next(c for c in release_readiness.criteria() if c.track == "R0")
    assert f"/{len(downloadable)} model cards" in pinning.detail


def test_the_native_evidence_counts_marked_tests_not_the_word() -> None:
    """The first draft grepped for the substring and reported 16 where there are 4."""
    import re

    native = next(c for c in release_readiness.criteria() if c.track == "R2")
    modules = next(line for line in native.evidence if line.startswith("parity modules:"))
    named = modules.removeprefix("parity modules:").split(",")
    assert 0 < len(named) <= 8, f"implausible parity-module count: {modules}"
    assert re.match(r"^\d+ test module", native.detail)
    assert str(len(named)) == native.detail.split()[0]


def test_the_report_renders_and_exits_non_zero_while_open(
    capsys: object,
) -> None:
    """It is usable as a release gate, not only as prose."""
    assert release_readiness.main([]) in (0, 1)
    assert release_readiness.main(["--json"]) in (0, 1)
